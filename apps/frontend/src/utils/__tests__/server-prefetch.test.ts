import { prefetch, prefetchList } from '../server-prefetch';
import { hasServerCapability } from '../server-permissions';

jest.mock('../server-permissions', () => ({
  hasServerCapability: jest.fn(),
}));

const mockHasCapability = hasServerCapability as jest.MockedFunction<
  typeof hasServerCapability
>;

/** A capability check that stays pending until `resolve` is called. */
function pendingCheck() {
  let resolve: (allowed: boolean) => void = () => undefined;
  mockHasCapability.mockReturnValue(
    new Promise<boolean>(r => {
      resolve = r;
    })
  );
  return (allowed: boolean) => resolve(allowed);
}

const flush = () => new Promise(r => setTimeout(r, 0));

describe('prefetch', () => {
  beforeEach(() => mockHasCapability.mockReset());

  it('starts the fetch before the capability check finishes', async () => {
    const finishCheck = pendingCheck();
    const fetch = jest.fn().mockResolvedValue({ id: 1 });

    const result = prefetch('thing:read', fetch);
    await flush();
    expect(fetch).toHaveBeenCalledTimes(1);

    finishCheck(true);
    await expect(result).resolves.toEqual({ id: 1 });
  });

  it('drops the fetched value when the capability is denied', async () => {
    mockHasCapability.mockResolvedValue(false);
    const fetch = jest.fn().mockResolvedValue({ secret: true });

    await expect(prefetch('thing:read', fetch)).resolves.toBeUndefined();
  });

  it('swallows a rejected fetch when the capability is denied', async () => {
    mockHasCapability.mockResolvedValue(false);
    const fetch = jest.fn().mockRejectedValue(new Error('403'));
    const unhandled = jest.fn();
    process.on('unhandledRejection', unhandled);

    await expect(prefetch('thing:read', fetch)).resolves.toBeUndefined();
    await flush();

    process.off('unhandledRejection', unhandled);
    expect(unhandled).not.toHaveBeenCalled();
  });

  it('returns undefined when an allowed fetch fails', async () => {
    mockHasCapability.mockResolvedValue(true);
    const fetch = jest.fn().mockRejectedValue(new Error('boom'));

    await expect(prefetch('thing:read', fetch)).resolves.toBeUndefined();
  });

  it('allows when any capability in a tuple is held', async () => {
    mockHasCapability.mockImplementation(async c => c === 'b:read');
    const fetch = jest.fn().mockResolvedValue('ok');

    await expect(prefetch(['a:read', 'b:read'], fetch)).resolves.toBe('ok');
  });
});

describe('prefetchList', () => {
  beforeEach(() => mockHasCapability.mockReset());

  const page = { data: [{ id: 1 }], pagination: { totalCount: 7 } };

  it('starts the fetch before the capability check finishes', async () => {
    const finishCheck = pendingCheck();
    const fetch = jest.fn().mockResolvedValue(page);

    const result = prefetchList('thing:read', fetch);
    await flush();
    expect(fetch).toHaveBeenCalledTimes(1);

    finishCheck(true);
    await expect(result).resolves.toEqual({
      initialData: [{ id: 1 }],
      initialTotalCount: 7,
    });
  });

  it('drops the page when the capability is denied', async () => {
    mockHasCapability.mockResolvedValue(false);
    const fetch = jest.fn().mockResolvedValue(page);

    await expect(prefetchList('thing:read', fetch)).resolves.toEqual({
      initialData: undefined,
      initialTotalCount: 0,
    });
  });
});
