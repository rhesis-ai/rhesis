/**
 * next/server needs the WHATWG Request/Response globals, which the default
 * jsdom environment does not provide.
 *
 * @jest-environment node
 */
import { GET } from '@/app/api/health/route';

describe('GET /api/health', () => {
  it('returns 200 with an ok status', async () => {
    const response = GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: 'ok' });
  });
});
