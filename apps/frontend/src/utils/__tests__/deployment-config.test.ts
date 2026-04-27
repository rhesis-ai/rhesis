import { readFileSync } from 'fs';
import path from 'path';

const frontendRoot = process.cwd();
const repoRoot = path.resolve(frontendRoot, '../..');

function readRepoFile(relativePath: string): string {
  return readFileSync(path.join(repoRoot, relativePath), 'utf8');
}

describe('frontend deployment config', () => {
  it('passes BACKEND_URL into the frontend image build for Next.js rewrites', () => {
    const dockerfile = readRepoFile('apps/frontend/Dockerfile');
    const workflow = readRepoFile('.github/workflows/frontend.yml');
    const compose = readRepoFile('docker-compose.yml');

    expect(dockerfile).toMatch(/\bARG BACKEND_URL\b/);
    expect(dockerfile).toMatch(/\bENV BACKEND_URL=\$\{BACKEND_URL\}/);
    expect(workflow).toMatch(/--build-arg BACKEND_URL=/);
    expect(compose).toMatch(/BACKEND_URL: \$\{BACKEND_URL:-http:\/\/backend:8080\}/);
  });

  it('keeps deployment and server-side backend URL usage on the shared resolver', () => {
    const workflow = readRepoFile('.github/workflows/frontend.yml');
    const k8sDeploy = readRepoFile('infrastructure/k8s/k8s-deploy.sh');
    const proxy = readRepoFile('apps/frontend/src/proxy.ts');
    const websocketRoute = readRepoFile(
      'apps/frontend/src/app/api/websocket-url/route.ts'
    );

    expect(workflow).toMatch(/BACKEND_API_URL="\$\{\{ secrets\.BACKEND_URL \}\}"/);
    expect(k8sDeploy).toMatch(/--build-arg BACKEND_URL="\$\{BACKEND_URL:-http:\/\/backend:8080\}"/);
    expect(proxy).toContain("new URL('/auth/logout', getServerBackendUrl())");
    expect(websocketRoute).toContain("import { getServerBackendUrl } from '@/utils/url-resolver';");
    expect(websocketRoute).toContain('deriveWebSocketUrl(getServerBackendUrl())');
  });
});
