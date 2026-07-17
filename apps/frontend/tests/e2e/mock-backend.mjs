/**
 * Minimal HTTP fixture server for local Playwright runs (E2E_NO_DOCKER).
 * Serves SSR and client API calls on port 8080 — no Docker required.
 */
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(__dirname, 'fixtures');
const PORT = Number(process.env.E2E_MOCK_BACKEND_PORT || 8080);

function loadJson(name) {
  return JSON.parse(fs.readFileSync(path.join(fixturesDir, name), 'utf8'));
}

const fixtures = {
  projects: loadJson('projects.json'),
  projectDetail: loadJson('project-detail.json'),
  tests: loadJson('tests.json'),
  testDetail: loadJson('test-detail.json'),
  testSets: loadJson('test-sets.json'),
  testSetDetail: loadJson('test-set-detail.json'),
  testRuns: loadJson('test-runs.json'),
  testRunDetail: loadJson('test-run-detail.json'),
  testResults: loadJson('test-results.json'),
  endpoints: loadJson('endpoints.json'),
  endpointDetail: loadJson('endpoint-detail.json'),
  knowledgeDetail: loadJson('knowledge-detail.json'),
  sources: loadJson('sources.json'),
  behaviors: loadJson('behaviors.json'),
  tasks: loadJson('tasks.json'),
  tokens: loadJson('tokens.json'),
};

const detailByResource = {
  projects: {
    'a1b2c3d4-0001-0001-0001-000000000001': fixtures.projectDetail,
  },
  tests: {
    'b1c2d3e4-0002-0002-0002-000000000001': fixtures.testDetail,
  },
  test_sets: {
    'c1d2e3f4-0003-0003-0003-000000000001': fixtures.testSetDetail,
  },
  test_runs: {
    'd1e2f3a4-0004-0004-0004-000000000001': fixtures.testRunDetail,
  },
  endpoints: {
    'f1a2b3c4-0006-0006-0006-000000000001': fixtures.endpointDetail,
  },
  sources: {
    'c2d3e4f5-0009-0009-0009-000000000001': fixtures.knowledgeDetail,
  },
  prompts: {
    'p1q2r3s4-0001-0001-0001-000000000001': {
      id: 'p1q2r3s4-0001-0001-0001-000000000001',
      content: 'Hello, please respond politely.',
    },
  },
};

const listByResource = {
  projects: fixtures.projects,
  tests: fixtures.tests,
  test_sets: fixtures.testSets,
  test_runs: fixtures.testRuns,
  test_results: fixtures.testResults,
  endpoints: fixtures.endpoints,
  sources: fixtures.sources,
  behaviors: fixtures.behaviors,
  tasks: fixtures.tasks,
  tokens: fixtures.tokens,
};

/** Sources created during a local no-docker E2E run. */
const uploadedSources = [];

const e2eUser = {
  ...loadJson('e2e-user.json'),
  is_superuser: false,
  is_email_verified: true,
};

function drainRequestBody(req) {
  return new Promise(resolve => {
    req.on('data', () => {});
    req.on('end', resolve);
  });
}

function sendJson(res, status, body, extraHeaders = {}) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers':
      'Authorization, Content-Type, X-Project-Id, Accept',
    'Access-Control-Expose-Headers': 'x-total-count',
    'Content-Length': Buffer.byteLength(payload),
    ...extraHeaders,
  });
  res.end(payload);
}

function sendList(res, items) {
  sendJson(res, 200, items, {
    'x-total-count': String(items.length),
    'access-control-expose-headers': 'x-total-count',
  });
}

function normalizePath(pathname) {
  return pathname.replace(/^\/api\/v1/, '') || '/';
}

function parseFilterId(searchParams) {
  const filter = searchParams.get('$filter') || '';
  const match = filter.match(/id eq ([0-9a-f-]+)/i);
  return match?.[1] ?? null;
}

function matchDetail(pathname) {
  for (const [resource, ids] of Object.entries(detailByResource)) {
    const prefix = `/${resource}/`;
    if (!pathname.startsWith(prefix)) continue;
    const rest = pathname.slice(prefix.length);
    const id = rest.split('/')[0];
    if (ids[id]) {
      return { resource, id, suffix: rest.slice(id.length), detail: ids[id] };
    }
  }
  return null;
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
      'Access-Control-Allow-Headers':
        'Authorization, Content-Type, X-Project-Id, Accept',
      'Access-Control-Max-Age': '86400',
    });
    res.end();
    return;
  }

  const url = new URL(req.url || '/', `http://127.0.0.1:${PORT}`);
  const pathname = normalizePath(url.pathname);
  const method = req.method || 'GET';

  if (method === 'GET' && pathname === '/health') {
    sendJson(res, 200, { status: 'ok' });
    return;
  }

  if (method === 'POST' && pathname === '/auth/verify') {
    sendJson(res, 200, { authenticated: true, user: e2eUser });
    return;
  }

  if (method === 'GET' && pathname === '/auth/terms-status') {
    sendJson(res, 200, { terms_accepted: true, has_prior_acceptance: true });
    return;
  }

  if (method === 'POST' && pathname === '/auth/accept-terms') {
    sendJson(res, 200, { success: true, terms_accepted: true });
    return;
  }

  if (method === 'GET' && pathname === '/features') {
    // Shape must match FeaturesResponse (utils/api-client/features-client.ts):
    // {license: {edition, licensed}, enabled: string[]}. Individual specs
    // override this route (e.g. RbacMockHelper.mockFeaturesEnabled) to turn
    // specific features on.
    sendJson(res, 200, {
      enabled: [],
      license: { edition: 'community', licensed: false },
    });
    return;
  }

  if (method === 'GET' && pathname === '/users/settings') {
    sendJson(res, 200, {
      ui: { theme: 'light' },
      models: {},
      notifications: {},
      default_project: { project_id: fixtures.projects[0]?.id ?? null },
    });
    return;
  }

  if (method === 'GET' && pathname === '/projects/mine') {
    sendList(res, fixtures.projects);
    return;
  }

  if (method === 'POST' && pathname === '/sources/upload') {
    drainRequestBody(req).then(() => {
      const source = {
        ...fixtures.knowledgeDetail,
        id: `e2e-upload-${Date.now()}`,
        title: 'E2E Uploaded Source',
        content: fixtures.knowledgeDetail.content,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      uploadedSources.push(source);
      sendJson(res, 200, source);
    });
    return;
  }

  const detail = matchDetail(pathname);
  if (detail && method === 'GET') {
    if (detail.suffix === '' || detail.suffix === '/') {
      sendJson(res, 200, detail.detail);
      return;
    }
    if (detail.resource === 'projects' && detail.suffix === '/members') {
      sendList(res, []);
      return;
    }
    if (
      detail.resource === 'projects' &&
      detail.suffix === '/parameters/schema'
    ) {
      sendJson(res, 200, { fields: [] });
      return;
    }
    if (detail.resource === 'projects' && detail.suffix === '/environments') {
      sendJson(res, 200, { environments: {} });
      return;
    }
    if (detail.resource === 'test_sets' && detail.suffix.startsWith('/tests')) {
      sendList(res, fixtures.tests);
      return;
    }
    if (
      detail.resource === 'test_runs' &&
      detail.suffix.startsWith('/results')
    ) {
      sendList(res, fixtures.testResults);
      return;
    }
    if (
      detail.resource === 'sources' &&
      (detail.suffix === '/content' || detail.suffix.startsWith('/content?'))
    ) {
      sendJson(res, 200, detail.detail);
      return;
    }
  }

  for (const [resource, items] of Object.entries(listByResource)) {
    if (
      method === 'GET' &&
      (pathname === `/${resource}` || pathname.startsWith(`/${resource}?`))
    ) {
      const filterId = parseFilterId(url.searchParams);
      const allItems =
        resource === 'sources' ? [...items, ...uploadedSources] : items;
      if (filterId) {
        const match = allItems.find(item => String(item.id) === filterId);
        sendList(res, match ? [match] : []);
        return;
      }
      sendList(res, allItems);
      return;
    }
  }

  if (method === 'GET' && pathname.startsWith('/type_lookups/')) {
    sendJson(res, 200, {
      id: pathname.split('/').pop(),
      type_value: 'functional',
    });
    return;
  }

  if (method === 'GET') {
    sendList(res, []);
    return;
  }

  sendJson(res, 405, { detail: 'Method not allowed' });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`E2E mock backend listening on http://127.0.0.1:${PORT}`);
});
