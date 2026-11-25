/**
 * @jest-environment node
 *
 * `backend-proxy` imports `next/server`, which needs the Web `Request` global
 * that the default jsdom environment does not provide.
 */
import { NextRequest } from 'next/server';
import type { Organization } from '@/utils/api-client/interfaces/organization';
import { proxyToBackend } from '../backend-proxy';
import {
  cachedOrganization,
  forgetOrganization,
  organizationWrittenBy,
} from '../organization-cache';

const org = (name: string) =>
  ({ id: 'org-1', name }) as unknown as Organization;

describe('cachedOrganization', () => {
  beforeEach(() => forgetOrganization('org-1'));
  afterEach(() => jest.useRealTimers());

  it('loads once per user and reuses the result', async () => {
    const load = jest.fn().mockResolvedValue(org('Acme'));

    await cachedOrganization('user-1', 'org-1', load);
    const second = await cachedOrganization('user-1', 'org-1', load);

    expect(second.name).toBe('Acme');
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('keeps users apart, since the response carries their permitted actions', async () => {
    const load = jest.fn().mockResolvedValue(org('Acme'));

    await cachedOrganization('user-1', 'org-1', load);
    await cachedOrganization('user-2', 'org-1', load);

    expect(load).toHaveBeenCalledTimes(2);
  });

  it('loads again once the entry has expired', async () => {
    jest.useFakeTimers();
    const load = jest.fn().mockResolvedValue(org('Acme'));

    await cachedOrganization('user-1', 'org-1', load);
    jest.advanceTimersByTime(31_000);
    await cachedOrganization('user-1', 'org-1', load);

    expect(load).toHaveBeenCalledTimes(2);
  });

  it('does not cache a failed load', async () => {
    const load = jest
      .fn()
      .mockRejectedValueOnce(new Error('backend down'))
      .mockResolvedValue(org('Acme'));

    await expect(cachedOrganization('user-1', 'org-1', load)).rejects.toThrow();
    await expect(cachedOrganization('user-1', 'org-1', load)).resolves.toEqual(
      org('Acme')
    );
  });
});

describe('organizationWrittenBy', () => {
  it.each([
    ['PUT', '/organizations/org-1', 'org-1'],
    ['PATCH', '/organizations/org-1/settings', 'org-1'],
    ['GET', '/organizations/org-1', null],
    ['PUT', '/projects/p-1', null],
  ])('%s %s -> %s', (method, path, expected) => {
    expect(organizationWrittenBy(method, path)).toBe(expected);
  });
});

describe('proxyToBackend and the organisation cache', () => {
  const fetchMock = jest.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
    forgetOrganization('org-1');
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  async function write(status: number) {
    fetchMock.mockResolvedValue(new Response(null, { status }));
    const req = new NextRequest(
      'https://app.example.com/api/backend/organizations/org-1',
      { method: 'PUT', body: '{}' }
    );
    await proxyToBackend(req, { backendPath: '/organizations/org-1' });
  }

  it('drops the cached organisation after a successful write', async () => {
    const load = jest.fn().mockResolvedValue(org('Acme'));
    await cachedOrganization('user-1', 'org-1', load);

    await write(200);
    await cachedOrganization('user-1', 'org-1', load);

    expect(load).toHaveBeenCalledTimes(2);
  });

  it('keeps it when the write failed', async () => {
    const load = jest.fn().mockResolvedValue(org('Acme'));
    await cachedOrganization('user-1', 'org-1', load);

    await write(422);
    await cachedOrganization('user-1', 'org-1', load);

    expect(load).toHaveBeenCalledTimes(1);
  });
});
