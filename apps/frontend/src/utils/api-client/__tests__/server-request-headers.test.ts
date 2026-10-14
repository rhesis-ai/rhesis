/**
 * @jest-environment node
 *
 * Server-side calls (no `window`) reach the backend directly, so the client
 * itself names the channel and passes on the browser's IP.
 */
import { BaseApiClient } from '../base-client';
import { provideServerRequestHeaders } from '../request-headers';

class ProbeClient extends BaseApiClient {
  headers(): Record<string, string> {
    return this.getHeaders() as Record<string, string>;
  }
}

describe('server-side request headers', () => {
  const env = process.env;

  beforeEach(() => {
    process.env = { ...env, BACKEND_URL: 'http://backend:8080' };
  });

  afterEach(() => {
    process.env = env;
    provideServerRequestHeaders(() => ({}));
  });

  it('marks server-side calls as the web client', () => {
    expect(new ProbeClient('token').headers()['x-rhesis-client']).toBe('web');
  });

  it("adds the request's browser IP when a source is registered", () => {
    provideServerRequestHeaders(() => ({
      'x-rhesis-client-ip': '203.0.113.7',
    }));

    expect(new ProbeClient('token').headers()['x-rhesis-client-ip']).toBe(
      '203.0.113.7'
    );
  });
});
