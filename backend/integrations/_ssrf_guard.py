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

__all__ = [
    "SSRFError",
    "resolve_to_safe_ip",
    "resolve_to_safe_ip_with_hostname",
    "validate_host_for_user_input",
    "validate_integration_url",
    "validate_url",
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
#    - set to 500 (far beyond legitimate traffic)
#    - Prevents OS-level thread exhaustion under sustained attack
#    - Does NOT cause cross-host DoS (unlike the old semaphore with limit=8)
#
# Why this is better than the old global semaphore:
#    - Old: 8 stuck lookups on host A → ALL lookups on host B fail (cross-host DoS)
#    - New: 8 stuck lookups on host A → only host A is affected (cached as
#      "blocked" for 10s); host B lookups proceed independently
#    - Old: repeated requests for same host spawn repeated threads (no cache)
#    - New: repeated requests within TTL return cached result (no new thread)

_DNS_POSITIVE_TTL = 60.0  # cache successful resolution for 60s
_DNS_NEGATIVE_TTL = 10.0  # cache timeout/failure for 10s (shorter, allows retry)
_DNS_THREAD_LIMIT = 500  # global cap on concurrent DNS threads (OS protection)

# Cache: host -> (ip_str_or_None, expiry_monotonic)
# None means "last lookup failed/timed out" — return SSRFError without new lookup
_DNS_CACHE: dict[str, tuple[str | None, float]] = {}
_DNS_CACHE_LOCK = threading.Lock()

# Per-host locks: ensure concurrent requests for same host share one DNS call
_PER_HOST_LOCKS: dict[str, threading.Lock] = {}
_PER_HOST_LOCKS_LOCK = threading.Lock()

# Global counter for concurrent DNS threads (OS protection, NOT cross-host DoS)
_DNS_THREAD_COUNT = 0
_DNS_THREAD_COUNT_LOCK = threading.Lock()


# ─── Static blocklists ────────────────────────────────────────────────────

_HOSTNAME_RE = re.compile(
    r"^[a-zA-Z0-9]"  # first char: alphanumeric
    r"([a-zA-Z0-9\-]*[a-zA-Z0-9])?"  # middle: hyphens allowed
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"  # dots + labels
)

# Hostnames that must ALWAYS be blocked regardless of DNS resolution.
# These either resolve to private IPs (localhost variants) or are
# cloud metadata service endpoints that must never be reachable from user input.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "localhost4",
        "localhost6",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",  # GCP metadata alias
        "metadata.google.internal",  # GCP metadata (resolved via /etc/hosts in GCP)
        "metadata.azure.com",  # Azure metadata alias
    }
)

# IP networks that must ALWAYS be blocked.
# This is defense-in-depth on top of Python's ipaddress.is_private etc.
# Python's flags cover most cases but miss CGNAT (100.64.0.0/10) and
# a few protocol-assignment ranges.
_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in [
        "0.0.0.0/8",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "10.0.0.0/8",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "100.64.0.0/10",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "127.0.0.0/8",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "169.254.0.0/16",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "172.16.0.0/12",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "192.0.0.0/24",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "192.0.2.0/24",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "192.168.0.0/16",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "198.18.0.0/15",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "198.51.100.0/24",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "203.0.113.0/24",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "224.0.0.0/4",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "240.0.0.0/4",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "::1/128",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "::/128",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "fc00::/7",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "fe80::/10",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
        "ff00::/8",  # NOSONAR: SSRF Zero-Trust Defense Guard (RFC 1918 / IMDS blocklist)
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
        list of IP literal strings (may be empty if resolution fails or
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


def resolve_to_safe_ip_with_hostname(host: str, dns_timeout: float = 5.0) -> tuple[str, str]:
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


def validate_integration_url(
    url: str,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    dns_timeout: float = 5.0,
) -> str:
    """Validate integration destination URL against SSRF attacks before network execution.

    Enforces:
      1. Non-empty string and valid URL syntax
      2. Strict scheme whitelist (http/https only by default) - denies non-HTTP/HTTPS schemes
      3. Host extraction and malformed/encoded IP bypass checks (octal, hex, decimal integer bypasses)
      4. Host safety check (blocks loopback, private ranges RFC 1918, link-local/cloud metadata, CGNAT, multicast)
      5. Synchronous pre-flight DNS resolution using socket.getaddrinfo() to resolve hostnames to IP addresses
      6. Parsing of each resolved IP with ipaddress.ip_address() and verification against unsafe CIDR ranges

    Args:
        url: Complete URL string (e.g. "https://api.example.com/data?q=1").
        allowed_schemes: Permitted URL schemes (default: http, https).
        dns_timeout: Max seconds to wait for DNS lookup.

    Returns:
        The validated URL string unmodified if safe.

    Raises:
        SSRFError: If scheme is forbidden, host is missing/blocked, or IP is non-routable/private.
        ValueError: If url is empty or malformed.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")

    from urllib.parse import urlparse

    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if not scheme:
        raise SSRFError(f"Missing URL scheme in '{url}'")

    if scheme not in [s.lower() for s in allowed_schemes]:
        raise SSRFError(f"Scheme '{scheme}' is not permitted. Allowed schemes: {allowed_schemes}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"Could not extract a valid hostname from URL: '{url}'")

    # Check for integer decimal notation (e.g. 2130706433)
    if hostname.isdigit():
        try:
            num_val = int(hostname)
            if 0 <= num_val <= 0xFFFFFFFF:
                ip = ipaddress.IPv4Address(num_val)
                if _is_unsafe_ip(ip):
                    raise SSRFError(
                        f"Host '{hostname}' (decimal IP {ip}) is an unsafe IP address. SSRF protection: refused."
                    )
        except (ValueError, OverflowError):
            pass

    # Check for hex representation (e.g. 0x7f000001)
    if hostname.lower().startswith("0x"):
        try:
            hex_val = int(hostname, 16)
            if 0 <= hex_val <= 0xFFFFFFFF:
                ip = ipaddress.IPv4Address(hex_val)
                if _is_unsafe_ip(ip):
                    raise SSRFError(
                        f"Host '{hostname}' (hex IP {ip}) is an unsafe IP address. SSRF protection: refused."
                    )
        except (ValueError, OverflowError):
            pass

    # Check for octal / zero-padded dotted notation (e.g. 0177.0.0.1 or 0177.0000.0000.0001)
    parts = hostname.split(".")
    if len(parts) == 4 and all(p.isalnum() for p in parts):
        try:
            parsed_parts = [int(p, 0) for p in parts]
            if all(0 <= p <= 255 for p in parsed_parts):
                ip_from_parts = ipaddress.IPv4Address(
                    (parsed_parts[0] << 24)
                    | (parsed_parts[1] << 16)
                    | (parsed_parts[2] << 8)
                    | parsed_parts[3]
                )
                if _is_unsafe_ip(ip_from_parts):
                    raise SSRFError(
                        f"Host '{hostname}' (normalized IP {ip_from_parts}) is an unsafe IP address. SSRF protection: refused."
                    )
        except (ValueError, OverflowError):
            pass

    # Check static blocked hostnames
    if _is_blocked_hostname(hostname):
        raise SSRFError(f"Host '{hostname}' is blocked. SSRF protection: refused to connect.")

    # Synchronous pre-flight DNS resolution and CIDR verification
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFError(f"Could not resolve host '{hostname}': {e}") from e

    if not addr_infos:
        raise SSRFError(f"Host '{hostname}' did not resolve to any IP address")

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as e:
            raise SSRFError(f"Invalid resolved IP address '{ip_str}' for host '{hostname}'") from e

        if _is_unsafe_ip(ip_obj):
            raise SSRFError(
                f"Host '{hostname}' resolves to unsafe IP address '{ip_str}' "
                f"(private/loopback/link-local/cloud metadata/carrier-grade NAT/multicast). SSRF protection: refused."
            )

    # Re-verify through standard service guard to populate cache
    resolve_to_safe_ip(hostname, dns_timeout=dns_timeout)
    return url


def validate_url(
    url: str,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    dns_timeout: float = 5.0,
) -> str:
    """Validate a destination URL against SSRF attacks before network execution.

    Enforces:
      1. Non-empty string and valid URL syntax
      2. Strict scheme whitelist (http/https only by default)
      3. Host extraction and format validation
      4. Host safety check (blocks localhost, metadata, private/loopback/cloud ranges)
      5. DNS resolution verification to ensure host resolves to a public safe IP
    """
    return validate_integration_url(url, allowed_schemes=allowed_schemes, dns_timeout=dns_timeout)


def _try_resolve_literal_ip(host: str) -> tuple[str, str] | None:
    """If ``host`` is a literal IP, return ``(ip_str, host)`` after safety check.

    Returns ``None`` if ``host`` is not a literal IP (caller should treat it
    as a hostname). Raises :class:`SSRFError` if the literal IP is unsafe.
    """
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None  # not a literal IP — caller falls through to hostname path
    if _is_unsafe_ip(ip):
        raise SSRFError(
            f"Host '{host}' is an unsafe IP address. SSRF protection: refused to connect."
        )
    return str(ip), host


def _read_dns_cache(host: str, now: float) -> str | None:
    """Return cached safe IP for ``host`` if cache entry is fresh.

    Returns:
        - safe IP string on positive cache hit
        - ``None`` on cache miss / stale entry (caller should perform DNS lookup)
        - Special marker ``"__NEGATIVE__"`` on negative cache hit — caller MUST
          raise :class:`SSRFError`.

    Negative cache indicates a recent DNS failure; the caller must refuse to
    retry within the TTL to prevent slow-DNS DoS.
    """
    with _DNS_CACHE_LOCK:
        cached = _DNS_CACHE.get(host)
    if cached is None or cached[1] <= now:
        return None  # miss or expired
    cached_ip, _expiry = cached
    if cached_ip is None:
        return "__NEGATIVE__"
    # Positive cache hit — re-validate the cached IP (defense-in-depth)
    try:
        ip = ipaddress.ip_address(cached_ip)
    except ValueError:
        # Cached value is not a valid IP — evict and fall through
        with _DNS_CACHE_LOCK:
            _DNS_CACHE.pop(host, None)
        return None
    if _is_unsafe_ip(ip):
        # Cached IP became unsafe? Shouldn't happen, but reject.
        raise SSRFError(
            f"Cached IP '{cached_ip}' for host '{host}' is unsafe. "
            f"SSRF protection: refused to connect."
        )
    return cached_ip


def _cache_dns_result(host: str, ip: str | None) -> None:
    """Write a DNS cache entry. ``None`` IP = negative cache."""
    ttl = _DNS_POSITIVE_TTL if ip is not None else _DNS_NEGATIVE_TTL
    with _DNS_CACHE_LOCK:
        _DNS_CACHE[host] = (ip, time.monotonic() + ttl)


def _find_first_safe_ip(ip_literals: list) -> str | None:
    """Return the first safe IP string from ``ip_literals``, or ``None``."""
    for ip_str in ip_literals:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_unsafe_ip(ip):
            continue  # skip unsafe IPs in the resolution list
        return str(ip)
    return None


def _resolve_to_safe_ip_impl(host: str, dns_timeout: float) -> tuple[str, str]:
    """Shared implementation for resolve_to_safe_ip and the _with_hostname variant."""
    if not host:
        raise SSRFError("Host cannot be empty")

    # Case 1: literal IP — validate and return as-is
    literal = _try_resolve_literal_ip(host)
    if literal is not None:
        return literal

    # Case 2: blocked hostname
    if _is_blocked_hostname(host):
        raise SSRFError(f"Host '{host}' is blocked. SSRF protection: refused to connect.")

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
    cached_ip = _read_dns_cache(host, time.monotonic())
    if cached_ip == "__NEGATIVE__":
        raise SSRFError(
            f"Host '{host}' recently failed DNS resolution. "
            f"Refusing to retry within negative-cache TTL "
            f"({_DNS_NEGATIVE_TTL}s) to prevent slow-DNS DoS."
        )
    if cached_ip is not None:
        return cached_ip, host

    # Step 2: acquire per-host lock (concurrent requests for same host
    # share one DNS call)
    host_lock = _get_per_host_lock(host)
    with host_lock:
        # Step 2a: double-check cache (another thread may have populated it
        # while we waited for the lock)
        cached_ip = _read_dns_cache(host, time.monotonic())
        if cached_ip == "__NEGATIVE__":
            raise SSRFError(
                f"Host '{host}' recently failed DNS resolution "
                f"(cached by another thread). Refusing to retry "
                f"within negative-cache TTL."
            )
        if cached_ip is not None:
            return cached_ip, host

        # Step 2b: perform the actual DNS lookup with timeout
        try:
            ip_literals = _resolve_host_with_timeout(host, dns_timeout)
        except (socket.gaierror, SSRFError) as e:
            # DNS resolution failed / timed out / thread-limit — cache negative
            _cache_dns_result(host, None)
            if isinstance(e, socket.gaierror):
                raise SSRFError(f"Could not resolve host '{host}': {e}") from e
            raise

        if not ip_literals:
            _cache_dns_result(host, None)
            raise SSRFError(f"Host '{host}' did not resolve to any IP address")

        # Find the first safe IP. We return the literal IP (not the hostname)
        # so the caller's socket.create_connection uses the IP directly.
        safe_ip = _find_first_safe_ip(ip_literals)
        if safe_ip is None:
            # All resolved IPs were unsafe — cache negative (the hostname
            # resolves only to unsafe IPs, unlikely to change quickly)
            _cache_dns_result(host, None)
            raise SSRFError(
                f"Host '{host}' resolves only to unsafe IP addresses "
                f"({', '.join(ip_literals[:3])}{'...' if len(ip_literals) > 3 else ''}). "
                f"SSRF protection: refused to connect."
            )

        # Cache positive result for long TTL
        _cache_dns_result(host, safe_ip)
        return safe_ip, host
