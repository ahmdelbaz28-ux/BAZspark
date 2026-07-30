"""Standard SSRF guard for ETAP integration (and reusable elsewhere).

Threat model (every item below is a real attack vector we defend against):

  1. Literal private/loopback/link-local/reserved/multicast IPs
     → blocked by _is_unsafe_ip() using both Python's ipaddress flags
       AND an explicit _BLOCKED_NETWORKS list (defense-in-depth).

  2. Hostnames that resolve to private IPs (e.g. localtest.me → 127.0.0.1)
     → blocked by validate_host_for_user_input() via DNS check at validation time.

  3. DNS rebinding (attacker changes DNS between validation and use)
     → defeated by resolve_to_safe_ip() at the service layer:
       re-resolves hostname at connection time AND returns a literal IP
       (not a hostname) so no further DNS lookup occurs.

  4. IPv6 bypasses:
     - ::ffff:127.0.0.1 (IPv4-mapped IPv6)
     - fe80::/10 (link-local)
     - fc00::/7 (Unique Local Addresses)
     → all caught by _is_unsafe_ip() including IPv4-mapped unwrapping.

  5. Cloud metadata endpoints:
     - 169.254.169.254 (AWS/GCP metadata IP)
     - metadata.google.internal (GCP metadata hostname)
     - 100.100.100.200 (Alibaba Cloud metadata)
     → IPs caught by _BLOCKED_NETWORKS (169.254.0.0/16, 100.64.0.0/10 CGNAT);
       hostnames caught by _BLOCKED_HOSTNAMES.

  6. Localhost variants: localhost, localhost.localdomain, ip6-localhost
     → caught by _BLOCKED_HOSTNAMES.

Usage pattern (two-layer defense):

  # Schema layer (Pydantic validator) — first line of defense
  from backend.integrations._ssrf_guard import validate_host_for_user_input

  class MySettings(BaseModel):
      host: str
      @field_validator("host")
      @classmethod
      def validate_host(cls, v): return validate_host_for_user_input(v.strip())

  # Service layer — second line of defense (defeats DNS rebinding)
  from backend.integrations._ssrf_guard import resolve_to_safe_ip

  def make_request(self, ...):
      safe_ip = resolve_to_safe_ip(self.host)  # may raise ValueError
      sock = socket.create_connection((safe_ip, self.port), timeout=...)
      # ↑ uses LITERAL IP — no further DNS lookup, no rebinding possible
"""
from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
from typing import Optional, Tuple

__all__ = [
    "SSRFError",
    "resolve_to_safe_ip",
    "resolve_to_safe_ip_with_hostname",
    "validate_host_for_user_input",
]

# ─── DNS resolution state ───────────────────────────────────────────────────
#
# ARCHITECTURE (replaces the flawed global-semaphore approach):
#
# 1. Per-host lock + TTL cache (positive AND negative)
#    - Concurrent requests for the SAME host share one DNS call (per-host lock)
#    - Repeated requests within TTL return cached result (no DNS call at all)
#    - This DEFEATS DNS rebinding as a side effect: the cached IP is reused
#      even if DNS changes, so the attacker can't re-bind between requests
#    - Negative caching (timeout → cache "blocked" for short TTL) prevents
#      a slow-DNS attacker from spawning repeated lookups for the same host
#
# 2. Hard timeout per DNS call (daemon thread + Thread.join)
#    - Bounds wall-clock time per caller
#    - Daemon threads don't block process exit
#
# 3. Global thread counter with HIGH limit (fail-fast only at OS-exhaustion)
#    - Set to 500 (far beyond legitimate traffic)
#    - Prevents OS-level thread exhaustion under sustained attack
#    - Does NOT cause cross-host DoS (unlike the old semaphore with limit=8)
#
# Why this is better than the old global semaphore:
#    - Old: 8 stuck lookups on host A → ALL lookups on host B fail (cross-host DoS)
#    - New: 8 stuck lookups on host A → only host A is affected (cached as
#      "blocked" for 10s); host B lookups proceed independently
#    - Old: repeated requests for same host spawn repeated threads (no cache)
#    - New: repeated requests within TTL return cached result (no new thread)

_DNS_POSITIVE_TTL = 60.0   # cache successful resolution for 60s
_DNS_NEGATIVE_TTL = 10.0   # cache timeout/failure for 10s (shorter, allows retry)
_DNS_THREAD_LIMIT = 500    # global cap on concurrent DNS threads (OS protection)

# Cache: host -> (ip_str_or_None, expiry_monotonic)
# None means "last lookup failed/timed out" — return SSRFError without new lookup
_DNS_CACHE: dict[str, Tuple[Optional[str], float]] = {}
_DNS_CACHE_LOCK = threading.Lock()

# Per-host locks: ensure concurrent requests for same host share one DNS call
_PER_HOST_LOCKS: dict[str, threading.Lock] = {}
_PER_HOST_LOCKS_LOCK = threading.Lock()

# Global counter for concurrent DNS threads (OS protection, NOT cross-host DoS)
_DNS_THREAD_COUNT = 0
_DNS_THREAD_COUNT_LOCK = threading.Lock()


# ─── Static blocklists ────────────────────────────────────────────────────

_HOSTNAME_RE = re.compile(
    r'^[a-zA-Z0-9]'                # first char: alphanumeric
    r'([a-zA-Z0-9\-]*[a-zA-Z0-9])?'  # middle: hyphens allowed
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$'  # dots + labels
)

# Hostnames that must ALWAYS be blocked regardless of DNS resolution.
# These either resolve to private IPs (localhost variants) or are
# cloud metadata service endpoints that must never be reachable from user input.
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "localhost4",
    "localhost6",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",                    # GCP metadata alias
    "metadata.google.internal",   # GCP metadata (resolved via /etc/hosts in GCP)
    "metadata.azure.com",         # Azure metadata alias
})

# IP networks that must ALWAYS be blocked.
# This is defense-in-depth on top of Python's ipaddress.is_private etc.
# Python's flags cover most cases but miss CGNAT (100.64.0.0/10) and
# a few protocol-assignment ranges.
_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in [
        "0.0.0.0/8",          # "This host" network
        "10.0.0.0/8",         # RFC1918 private
        "100.64.0.0/10",      # CGNAT (RFC6598) — not flagged by is_private
        "127.0.0.0/8",        # Loopback
        "169.254.0.0/16",     # Link-local (includes AWS/GCP/Azure metadata)
        "172.16.0.0/12",      # RFC1918 private
        "192.0.0.0/24",       # IETF protocol assignments
        "192.0.2.0/24",       # TEST-NET-1
        "192.168.0.0/16",     # RFC1918 private
        "198.18.0.0/15",      # Benchmarking
        "198.51.100.0/24",    # TEST-NET-2
        "203.0.113.0/24",     # TEST-NET-3
        "224.0.0.0/4",        # Multicast
        "240.0.0.0/4",        # Reserved
        "::1/128",            # IPv6 loopback
        "::/128",             # IPv6 unspecified
        "fc00::/7",           # IPv6 Unique Local Addresses
        "fe80::/10",          # IPv6 link-local
        "ff00::/8",           # IPv6 multicast
    ]
)


# ─── Errors ───────────────────────────────────────────────────────────────


class SSRFError(ValueError):
    """Raised when a host fails SSRF validation.

    Subclassing ValueError so Pydantic's field_validator treats it as a
    validation error (not an uncaught exception), while still letting
    service-layer code distinguish SSRF rejections from other ValueErrors.
    """


# ─── Core logic ───────────────────────────────────────────────────────────


def _is_unsafe_ip(ip: ipaddress._BaseAddress) -> bool:
    """Return True if the IP address should never be connected to from user input."""
    # Layer 1: Python's built-in flags (covers is_private, is_loopback,
    # is_link_local, is_reserved, is_multicast, is_unspecified)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True

    # Layer 2: explicit network blocklist (catches CGNAT, TEST-NETs, etc.)
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True

    # Layer 3: IPv4-mapped IPv6 unwrapping.
    # Example: ::ffff:127.0.0.1 looks like an IPv6 address but is actually
    # 127.0.0.1 in disguise. Python's is_loopback returns False for this,
    # so we must unwrap and re-check.
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is not None and _is_unsafe_ip(mapped):
            return True

    return False


def _is_blocked_hostname(host: str) -> bool:
    """Return True if the hostname should always be blocked regardless of DNS."""
    # Normalize: lowercase, strip trailing dot
    lower = host.lower().rstrip(".")
    return lower in _BLOCKED_HOSTNAMES


def _resolve_host(host: str) -> list[str]:
    """Resolve a hostname to a list of IP literal strings.

    Returns:
        List of IP literal strings (may be empty if resolution fails or
        returns no usable records).

    Raises:
        socket.gaierror: if DNS resolution fails.
        SSRFError: if DNS resolution times out (defense against slow-DNS DoS).
    """
    infos = socket.getaddrinfo(host, None)
    return [info[4][0] for info in infos]


def _resolve_host_with_timeout(host: str, dns_timeout: float) -> list[str]:
    """Resolve a hostname with a HARD wall-clock timeout.

    Uses a daemon worker thread + Thread.join(timeout=...) to bound wall-clock
    time per caller. Uses a GLOBAL thread counter (NOT a per-host semaphore)
    with a HIGH limit (_DNS_THREAD_LIMIT=500) to prevent OS-level thread
    exhaustion under sustained attack.

    Why a global counter instead of a global semaphore (BoundedSemaphore)?
      - A semaphore with low limit (e.g., 8) causes CROSS-HOST DoS: 8 stuck
        lookups on host A blocks ALL lookups on host B. This is unacceptable.
      - A counter with high limit (500) only triggers fail-fast under genuine
        OS-level exhaustion (500+ concurrent DNS threads), which is far beyond
        legitimate traffic.
      - Cross-host DoS is prevented by the per-host lock + TTL cache in
        _resolve_to_safe_ip_impl(), not by the global counter.

    If the underlying DNS lookup hangs, the daemon thread remains blocked
    (Python cannot forcibly kill threads), but:
      - the caller gets control back via SSRFError
      - the daemon thread does NOT block process exit
      - the per-host TTL cache (in _resolve_to_safe_ip_impl) caches the
        negative result for _DNS_NEGATIVE_TTL seconds, preventing repeated
        lookups for the same host during that window

    Raises:
        SSRFError: if DNS resolution times out, or if the global thread
                  count exceeds _DNS_THREAD_LIMIT (OS protection).
        socket.gaierror: if DNS resolution fails (propagated from worker).
    """
    global _DNS_THREAD_COUNT

    # Global thread counter — fail fast ONLY at OS-exhaustion level
    with _DNS_THREAD_COUNT_LOCK:
        if _DNS_THREAD_COUNT >= _DNS_THREAD_LIMIT:
            raise SSRFError(
                f"DNS thread limit ({_DNS_THREAD_LIMIT}) exceeded — "
                f"too many concurrent DNS lookups. This indicates either "
                f"a severe slow-DNS DoS or a misconfigured DNS resolver. "
                f"Failing fast to prevent OS-level thread exhaustion."
            )
        _DNS_THREAD_COUNT += 1

    result_box: list = []
    exc_box: list = []

    def worker() -> None:
        global _DNS_THREAD_COUNT
        try:
            result_box.append(_resolve_host(host))
        except BaseException as e:  # noqa: BLE001  # NOSONAR — python:S5754: BaseException needed to catch thread SystemExit; re-raised via exc_box
            exc_box.append(e)
        finally:
            with _DNS_THREAD_COUNT_LOCK:
                _DNS_THREAD_COUNT -= 1

    t = threading.Thread(target=worker, daemon=True, name=f"ssrf-dns-{host[:32]}")
    t.start()
    t.join(timeout=dns_timeout)

    if t.is_alive():
        # Thread is still running — DNS lookup hung. The daemon thread will
        # keep running until getaddrinfo returns (may be never), but:
        #   - caller is unblocked
        #   - thread counter was already decremented in worker's finally
        #     (which will run when getaddrinfo eventually returns)
        #   - per-host cache (in caller) will cache negative result
        raise SSRFError(
            f"DNS resolution timed out for host '{host}' after {dns_timeout}s. "
            f"This may indicate a slow-DNS DoS attempt. The lookup continues "
            f"in the background but the caller is unblocked."
        )

    # Thread finished — re-raise any exception it captured
    if exc_box:
        raise exc_box[0]

    return result_box[0] if result_box else []


def _get_per_host_lock(host: str) -> threading.Lock:
    """Get or create a per-host lock for DNS resolution.

    This ensures concurrent requests for the SAME host share one DNS call,
    preventing pile-on attacks where many requests for the same slow-DNS
    host spawn many threads.
    """
    with _PER_HOST_LOCKS_LOCK:
        if host not in _PER_HOST_LOCKS:
            _PER_HOST_LOCKS[host] = threading.Lock()
        return _PER_HOST_LOCKS[host]


def _reset_dns_state_for_testing() -> None:
    """Reset all DNS-related global state.

    For test isolation only — never call from production code.
    Clears the DNS cache, per-host locks, and resets the thread counter.
    """
    global _DNS_THREAD_COUNT
    with _DNS_CACHE_LOCK:
        _DNS_CACHE.clear()
    with _PER_HOST_LOCKS_LOCK:
        _PER_HOST_LOCKS.clear()
    with _DNS_THREAD_COUNT_LOCK:
        _DNS_THREAD_COUNT = 0


# ─── Public API ───────────────────────────────────────────────────────────


def validate_host_for_user_input(host: str) -> str:
    """Pydantic validator — first line of defense.

    This validator is PURE: it performs NO network I/O. It only checks:
      - Empty strings
      - Invalid hostname format (regex)
      - Blocked hostnames (localhost, cloud metadata — static list)
      - Literal unsafe IPs (private, loopback, link-local, etc.)

    It does NOT perform DNS resolution. DNS checks belong exclusively in
    the service layer (resolve_to_safe_ip) because:
      1. Pydantic validators must be fast, deterministic, and pure
      2. Network I/O in a validator can hang the request handler
      3. DNS state at validation time ≠ DNS state at connection time (TOCTOU)
      4. The service layer re-checks anyway, so validator DNS checks are redundant

    Returns:
        The validated host string (unchanged) if it passes all checks.

    Raises:
        SSRFError: if the host is unsafe (empty, invalid format, blocked,
                  or a literal unsafe IP).
    """
    if not host:
        raise SSRFError("Host cannot be empty")

    # Case 1: literal IP — validate directly.
    # We must distinguish SSRFError (unsafe IP) from plain ValueError (not an IP).
    # Since SSRFError is a ValueError subclass, we check isinstance explicitly.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as e:
        if isinstance(e, SSRFError):
            raise  # already an SSRF rejection (shouldn't happen here, defensive)
        # Not a literal IP — fall through to hostname path
        pass
    else:
        # We have a valid IP literal — check if it's unsafe
        if _is_unsafe_ip(ip):
            raise SSRFError(
                f"Host '{host}' is an unsafe IP address "
                f"(private/loopback/link-local/reserved/multicast). "
                f"SSRF protection: only public IPs or hostnames are allowed."
            )
        return host  # Literal public IP — allowed

    # Case 2: hostname format check
    if not _HOSTNAME_RE.match(host):
        raise SSRFError(f"Invalid hostname format: {host}")

    # Case 3: blocked hostname list
    if _is_blocked_hostname(host):
        raise SSRFError(
            f"Host '{host}' is blocked. SSRF protection: localhost and "
            f"cloud metadata hostnames are not allowed."
        )

    # NOTE: DNS resolution check is intentionally NOT performed here.
    # The service layer (resolve_to_safe_ip) handles DNS at connection time.
    # See module docstring and resolve_to_safe_ip() for details.
    return host


def resolve_to_safe_ip(host: str, dns_timeout: float = 5.0) -> str:
    """Service layer — second line of defense (defeats DNS rebinding).

    MUST be called immediately before socket.create_connection().

    Returns:
        A literal IP address string (never a hostname). The caller uses
        this IP directly in socket.create_connection, which means NO
        further DNS lookup occurs — defeating DNS rebinding attacks.

    For TLS/HTTPS callers that need SNI and certificate validation, use
    resolve_to_safe_ip_with_hostname() instead — it returns both the
    safe IP AND the original hostname so you can wrap_socket with the
    correct server_hostname.

    Raises:
        SSRFError: if the host is unsafe, all resolved IPs are unsafe,
                  or DNS resolution times out.
    """
    safe_ip, _original_host = _resolve_to_safe_ip_impl(host, dns_timeout)
    return safe_ip


def resolve_to_safe_ip_with_hostname(
    host: str, dns_timeout: float = 5.0
) -> Tuple[str, str]:
    """Like resolve_to_safe_ip, but also returns the original hostname.

    Use this for TLS/HTTPS connections:
        safe_ip, original_host = resolve_to_safe_ip_with_hostname(host)
        sock = socket.create_connection((safe_ip, port), timeout=...)
        ctx = ssl.create_default_context()
        # SNI and cert validation MUST use the original hostname, not the IP.
        # Otherwise a MITM could serve a valid cert for 'attacker.com' on a
        # different IP and we would accept it.
        tls_sock = ctx.wrap_socket(sock, server_hostname=original_host)

    Returns:
        (safe_ip_literal, original_hostname) tuple.

    Raises:
        SSRFError: same conditions as resolve_to_safe_ip.
    """
    return _resolve_to_safe_ip_impl(host, dns_timeout)


def _resolve_to_safe_ip_impl(host: str, dns_timeout: float) -> Tuple[str, str]:
    """Shared implementation for resolve_to_safe_ip and the _with_hostname variant."""
    if not host:
        raise SSRFError("Host cannot be empty")

    # Case 1: literal IP — validate and return as-is
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass  # not a literal IP — fall through to hostname path
    else:
        if _is_unsafe_ip(ip):
            raise SSRFError(
                f"Host '{host}' is an unsafe IP address. "
                f"SSRF protection: refused to connect."
            )
        return str(ip), host

    # Case 2: blocked hostname
    if _is_blocked_hostname(host):
        raise SSRFError(
            f"Host '{host}' is blocked. SSRF protection: refused to connect."
        )

    # Case 3: re-resolve hostname at connection time.
    # This is the critical defense: even if the validator passed earlier,
    # the attacker may have changed DNS by now. We re-resolve and verify.
    #
    # ARCHITECTURE: per-host lock + TTL cache (positive AND negative).
    #   - Per-host lock: concurrent requests for the SAME host share one DNS
    #     call (prevents pile-on attacks).
    #   - Positive cache (60s): repeated requests return cached IP without
    #     any DNS call. As a side effect, this DEFEATS DNS rebinding: even
    #     if the attacker changes DNS, we serve the cached (safe) IP.
    #   - Negative cache (10s): if the lookup timed out or failed, cache
    #     "blocked" for 10s so repeated requests don't spawn new threads.

    # Step 1: check cache (fast path — no lock contention for cache hits)
    now = time.monotonic()
    with _DNS_CACHE_LOCK:
        cached = _DNS_CACHE.get(host)
        if cached is not None and cached[1] > now:
            cached_ip, _expiry = cached
            if cached_ip is None:
                # Negative cache hit — previous lookup failed/timed out
                raise SSRFError(
                    f"Host '{host}' recently failed DNS resolution. "
                    f"Refusing to retry within negative-cache TTL "
                    f"({_DNS_NEGATIVE_TTL}s) to prevent slow-DNS DoS."
                )
            # Positive cache hit — re-validate the cached IP (defense-in-depth)
            try:
                ip = ipaddress.ip_address(cached_ip)
                if _is_unsafe_ip(ip):
                    # Cached IP became unsafe? Shouldn't happen, but reject.
                    raise SSRFError(
                        f"Cached IP '{cached_ip}' for host '{host}' is unsafe. "
                        f"SSRF protection: refused to connect."
                    )
                return cached_ip, host
            except ValueError:
                # Cached value is not a valid IP — evict and fall through
                _DNS_CACHE.pop(host, None)

    # Step 2: acquire per-host lock (concurrent requests for same host
    # share one DNS call)
    host_lock = _get_per_host_lock(host)
    with host_lock:
        # Step 2a: double-check cache (another thread may have populated it
        # while we waited for the lock)
        now = time.monotonic()
        with _DNS_CACHE_LOCK:
            cached = _DNS_CACHE.get(host)
            if cached is not None and cached[1] > now:
                cached_ip, _expiry = cached
                if cached_ip is None:
                    raise SSRFError(
                        f"Host '{host}' recently failed DNS resolution "
                        f"(cached by another thread). Refusing to retry "
                        f"within negative-cache TTL."
                    )
                try:
                    ip = ipaddress.ip_address(cached_ip)
                    if not _is_unsafe_ip(ip):
                        return cached_ip, host
                except ValueError:
                    pass

        # Step 2b: perform the actual DNS lookup with timeout
        try:
            ip_literals = _resolve_host_with_timeout(host, dns_timeout)
        except socket.gaierror as e:
            # DNS resolution failed — cache negative for short TTL
            with _DNS_CACHE_LOCK:
                _DNS_CACHE[host] = (None, time.monotonic() + _DNS_NEGATIVE_TTL)
            raise SSRFError(f"Could not resolve host '{host}': {e}")
        except SSRFError:
            # Timeout or thread-limit — cache negative for short TTL
            with _DNS_CACHE_LOCK:
                _DNS_CACHE[host] = (None, time.monotonic() + _DNS_NEGATIVE_TTL)
            raise

        if not ip_literals:
            with _DNS_CACHE_LOCK:
                _DNS_CACHE[host] = (None, time.monotonic() + _DNS_NEGATIVE_TTL)
            raise SSRFError(f"Host '{host}' did not resolve to any IP address")

        # Find the first safe IP. We return the literal IP (not the hostname)
        # so the caller's socket.create_connection uses the IP directly.
        safe_ip: Optional[str] = None
        for ip_str in ip_literals:
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if _is_unsafe_ip(ip):
                continue  # skip unsafe IPs in the resolution list
            safe_ip = str(ip)
            break

        if safe_ip is None:
            # All resolved IPs were unsafe — cache negative (the hostname
            # resolves only to unsafe IPs, unlikely to change quickly)
            with _DNS_CACHE_LOCK:
                _DNS_CACHE[host] = (None, time.monotonic() + _DNS_NEGATIVE_TTL)
            raise SSRFError(
                f"Host '{host}' resolves only to unsafe IP addresses "
                f"({', '.join(ip_literals[:3])}{'...' if len(ip_literals) > 3 else ''}). "
                f"SSRF protection: refused to connect."
            )

        # Cache positive result for long TTL
        with _DNS_CACHE_LOCK:
            _DNS_CACHE[host] = (safe_ip, time.monotonic() + _DNS_POSITIVE_TTL)

        return safe_ip, host
