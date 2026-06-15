import { fetchQuickStartEnabled } from '../quick_start';

function makeResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: () => Promise.resolve(body),
  } as Response;
}

describe('quick_start', () => {
  describe('fetchQuickStartEnabled', () => {
    let fetchMock: jest.Mock;

    beforeEach(() => {
      fetchMock = jest.fn();
      global.fetch = fetchMock;
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('returns true when the backend enables Quick Start', async () => {
      fetchMock.mockResolvedValue(makeResponse({ quick_start: true }));

      await expect(fetchQuickStartEnabled()).resolves.toBe(true);
      expect(fetchMock).toHaveBeenCalledWith('/api/auth-config');
    });

    it('returns false when the backend disables Quick Start', async () => {
      fetchMock.mockResolvedValue(makeResponse({ quick_start: false }));

      await expect(fetchQuickStartEnabled()).resolves.toBe(false);
    });

    it('returns false when the backend omits Quick Start status', async () => {
      fetchMock.mockResolvedValue(makeResponse({}));

      await expect(fetchQuickStartEnabled()).resolves.toBe(false);
    });

    it('returns false when the auth config request fails', async () => {
      fetchMock.mockResolvedValue(makeResponse({}, false));

      await expect(fetchQuickStartEnabled()).resolves.toBe(false);
    });

    it('returns false when fetching auth config throws', async () => {
      fetchMock.mockRejectedValue(new Error('network unavailable'));

      await expect(fetchQuickStartEnabled()).resolves.toBe(false);
    });
  });
});
