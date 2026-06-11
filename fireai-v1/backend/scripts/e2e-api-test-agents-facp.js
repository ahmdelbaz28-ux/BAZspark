/**
 * Local API smoke/e2e tests for FireAI v1 backend.
 * Targets:
 *  - /api/agents
 *  - /api/agents/:id
 *  - /api/agents/stats
 *  - /api/agents/:id/capabilities
 *  - /api/agents/:id/status (PUT)
 *  - /api/agents/:id/task (POST)
 *  - /api/facp/request (POST)
 *  - /api/facp/executions (GET + limit)
 *  - /api/facp/executions/:id (GET)
 *  - /api/facp/metrics (GET)
 *  - /api/facp/health (GET)
 *  - /api/facp/spec (GET)
 *
 * Usage:
 *  node scripts/e2e-api-test-agents-facp.js
 *
 * Assumes backend is already running on http://localhost:8000
 */

const base = process.env.BASE_URL || 'http://localhost:8000';

function safePickId(agents) {
  if (!Array.isArray(agents) || agents.length === 0) return null;
  const a = agents[0];
  return a?.id ?? a?.agentId ?? a?._id ?? null;
}

async function fetchText(url, opts) {
  const r = await fetch(url, opts);
  const text = await r.text();
  return { status: r.status, text, headers: Object.fromEntries(r.headers.entries()) };
}

async function fetchJson(url, opts) {
  const r = await fetch(url, opts);
  const text = await r.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch (_) {
    // keep json null
  }
  return { status: r.status, json, text };
}

function logBlock(title) {
  console.log('\n========================');
  console.log(title);
  console.log('========================');
}

(async () => {
  console.log('BASE_URL =', base);

  // Agents: list
  logBlock('GET /api/agents');
  const agentsResp = await fetchJson(base + '/api/agents');
  console.log('HTTP', agentsResp.status);
  if (agentsResp.json) {
    console.log('payload keys:', Object.keys(agentsResp.json));
    console.log('count:', agentsResp.json.count);
    console.log('agents:', agentsResp.json.agents);
  } else {
    console.log('non-json response:', agentsResp.text.slice(0, 500));
  }

  const agents = agentsResp.json?.agents;
  const id = safePickId(agents);
  console.log('picked agent id =', id);

  const idBad = '999999';

  // Agents: get by id
  if (id) {
    logBlock(`GET /api/agents/:id (valid) -> ${id}`);
    const r1 = await fetchText(base + '/api/agents/' + encodeURIComponent(id));
    console.log('HTTP', r1.status);
    console.log(r1.text.slice(0, 600));
  }

  logBlock(`GET /api/agents/:id (invalid) -> ${idBad}`);
  const r2 = await fetchText(base + '/api/agents/' + encodeURIComponent(idBad));
  console.log('HTTP', r2.status);
  console.log(r2.text.slice(0, 600));

  // Agents: stats
  logBlock('GET /api/agents/stats');
  const r3 = await fetchJson(base + '/api/agents/stats');
  console.log('HTTP', r3.status);
  console.log(r3.json ?? r3.text.slice(0, 600));

  // Agents: capabilities
  if (id) {
    logBlock(`GET /api/agents/:id/capabilities (valid) -> ${id}`);
    const r4 = await fetchJson(base + '/api/agents/' + encodeURIComponent(id) + '/capabilities');
    console.log('HTTP', r4.status);
    console.log(r4.json ?? r4.text.slice(0, 600));
  }

  logBlock(`GET /api/agents/:id/capabilities (invalid) -> ${idBad}`);
  const r5 = await fetchText(base + '/api/agents/' + encodeURIComponent(idBad) + '/capabilities');
  console.log('HTTP', r5.status);
  console.log(r5.text.slice(0, 600));

  // Agents: status PUT
  if (id) {
    logBlock(`PUT /api/agents/:id/status valid -> ${id}`);
    const r6 = await fetchJson(base + '/api/agents/' + encodeURIComponent(id) + '/status', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'busy' })
    });
    console.log('HTTP', r6.status);
    console.log(r6.json ?? r6.text.slice(0, 600));

    logBlock(`PUT /api/agents/:id/status invalid status -> ${id}`);
    const r7 = await fetchJson(base + '/api/agents/' + encodeURIComponent(id) + '/status', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'nope' })
    });
    console.log('HTTP', r7.status);
    console.log(r7.json ?? r7.text.slice(0, 600));
  }

  // Agents: task POST
  if (id) {
    logBlock(`POST /api/agents/:id/task valid -> ${id}`);
    const r8 = await fetchJson(base + '/api/agents/' + encodeURIComponent(id) + '/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task: { id: 't1', type: 'demo', description: 'hello' } })
    });
    console.log('HTTP', r8.status);
    console.log(r8.json ?? r8.text.slice(0, 600));

    logBlock(`POST /api/agents/:id/task invalid body -> ${id}`);
    const r9 = await fetchJson(base + '/api/agents/' + encodeURIComponent(id) + '/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task: 'bad' })
    });
    console.log('HTTP', r9.status);
    console.log(r9.json ?? r9.text.slice(0, 600));
  }

  // FACP: health/spec/metrics
  logBlock('GET /api/facp/health');
  const f1 = await fetchJson(base + '/api/facp/health');
  console.log('HTTP', f1.status);
  console.log(f1.json ?? f1.text.slice(0, 600));

  logBlock('GET /api/facp/spec');
  const f2 = await fetchJson(base + '/api/facp/spec');
  console.log('HTTP', f2.status);
  console.log(f2.json ?? f2.text.slice(0, 600));

  logBlock('GET /api/facp/metrics');
  const f3 = await fetchJson(base + '/api/facp/metrics');
  console.log('HTTP', f3.status);
  console.log(f3.json ?? f3.text.slice(0, 600));

  // FACP: executions list
  logBlock('GET /api/facp/executions?limit=5');
  const f4 = await fetchJson(base + '/api/facp/executions?limit=5');
  console.log('HTTP', f4.status);
  console.log(f4.json ?? f4.text.slice(0, 600));

  // FACP: submit a request (best-effort)
  // Note: This endpoint requires security+params objects per validators.
  // We use a minimal plausible payload; backend may reject depending on implementation.
  logBlock('POST /api/facp/request (best-effort minimal payload)');
  const payload = {
    protocol: 'FACP',
    id: 'req-local-1',
    method: 'NOOP',
    params: { test: true },
    security: { auth_token: 'local-dev', permissions: ['read'] }
  };

  const f5 = await fetchJson(base + '/api/facp/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  console.log('HTTP', f5.status);
  console.log(f5.json ?? f5.text.slice(0, 800));

  // If we got traces/executions, try execution by id.
  const after = await fetchJson(base + '/api/facp/executions?limit=5');
  const firstTraceId = after.json?.traces?.[0]?.id ?? after.json?.traces?.[0]?._id ?? null;

  if (firstTraceId) {
    logBlock('GET /api/facp/executions/:id');
    const f6 = await fetchJson(base + '/api/facp/executions/' + encodeURIComponent(firstTraceId));
    console.log('HTTP', f6.status);
    console.log(f6.json ?? f6.text.slice(0, 600));
  } else {
    console.log('\nNo executions trace id available to test /api/facp/executions/:id');
  }

  console.log('\nDONE');
})().catch((e) => {
  console.error('E2E TEST SCRIPT FAILED:', e);
  process.exit(1);
});
