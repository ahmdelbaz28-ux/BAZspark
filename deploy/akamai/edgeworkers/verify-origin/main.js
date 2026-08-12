// ─────────────────────────────────────────────────────────────────────────
// EdgeWorker: verify-origin
// ─────────────────────────────────────────────────────────────────────────
// Verifies that requests arriving at the origin have transited the Akamai
// Edge by injecting a shared secret (X-Akamai-Origin-Token header) that
// backend/akamai_middleware.py validates.
//
// This prevents attackers from bypassing the WAF/Bot Manager by sending
// traffic directly to the HF Space / Vercel origin URL.
//
// Install: upload to Akamai EdgeWorkers via API or Control Center, then
// bind to the property via Property Manager → behaviors → edgeworker.
//
// Bundle: this file goes into the /src directory of the EdgeWorker bundle.
// See: https://techdocs.akamai.com/edgeworkers/docs/getting-started
// ─────────────────────────────────────────────────────────────────────────

import { URL } from 'node:url';

// Paths that are always allowed (health checks, public endpoints).
const PUBLIC_PATHS = ['/api/health', '/api/v1/health', '/favicon.ico', '/robots.txt'];

export function onClientRequest(request) {
    const path = new URL(request.url).pathname;

    // P0-15 FIX: the shared secret now comes from a Property Manager variable
    // (PMUSER_origin_token), never from source code. If the variable is unset
    // we FAIL CLOSED with 403 — an EdgeWorker silently injecting a placeholder
    // token would let direct-to-origin traffic pass the backend check.
    const ORIGIN_TOKEN = request.getVariable('PMUSER_origin_token') || '';
    if (!ORIGIN_TOKEN) {
        request.respondWith(403, {}, 'Forbidden: origin token not configured');
        return;
    }

    // Skip verification for public paths
    if (PUBLIC_PATHS.some(p => path === p || path.startsWith(p + '/'))) {
        request.addHeader('X-Akamai-Origin-Token', ORIGIN_TOKEN);
        request.addHeader('X-Akamai-EdgeWorker', 'verify-origin');
        return;
    }

    // Inject the origin verification token + edge metadata
    request.addHeader('X-Akamai-Origin-Token', ORIGIN_TOKEN);
    request.addHeader('X-Akamai-EdgeWorker', 'verify-origin');
    request.addHeader('X-Akamai-EdgeWorker-Version', '1.0.0');
    request.addHeader('X-Akamai-Request-Start-Time', new Date().toISOString());

    // Detect suspicious patterns at the edge (early rejection)
    const suspiciousHeaders = detectSuspiciousHeaders(request);
    if (suspiciousHeaders.length > 0) {
        request.addHeader('X-Akamai-Suspicious-Headers', suspiciousHeaders.join(','));
        // Don't block here — let WAF/Bot Manager decide based on combined signals
    }

    // Pass through to origin (implicit return)
}

export function onOriginResponse(request, response) {
    // Add traceability header to the response so the client can correlate
    // the request across Akamai → origin → database.
    response.addHeader('X-Akamai-EdgeWorker-Processed', 'true');
    response.addHeader('X-Akamai-Origin-Response-Time', new Date().toISOString());
}

function detectSuspiciousHeaders(request) {
    const suspicious = [];
    const ua = request.getHeader('User-Agent') || '';

    // Common attack tool signatures
    const attackTools = ['sqlmap', 'nikto', 'masscan', 'nmap', 'wpscan', 'metasploit', 'hydra'];
    if (attackTools.some(t => ua.toLowerCase().includes(t))) {
        suspicious.push('attack-tool-ua');
    }

    // Missing User-Agent
    if (!ua) {
        suspicious.push('missing-ua');
    }

    // Suspicious X-Forwarded-For (attempt to spoof True-Client-IP)
    const xff = request.getHeader('X-Forwarded-For') || '';
    if (xff && xff.split(',').length > 5) {
        suspicious.push('xff-chain-too-long');
    }

    // Suspicious Referer
    const referer = request.getHeader('Referer') || '';
    if (referer && (referer.includes('ahmdelbaz28-bazspark.hf.space') || referer.includes('vercel.app'))) {
        suspicious.push('direct-origin-referer');
    }

    return suspicious;
}
