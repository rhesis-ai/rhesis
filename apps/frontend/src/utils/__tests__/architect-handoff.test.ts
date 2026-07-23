import {
  clearPendingHandoffMessage,
  createAndOpenArchitectSession,
  peekPendingHandoffMessage,
  takePendingHandoffMessage,
} from '../architect-handoff';

const createSession = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getArchitectClient: () => ({
      createSession,
    }),
  })),
}));

function createMockStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => (map.has(key) ? (map.get(key) as string) : null),
    key: (index: number) => Array.from(map.keys())[index] ?? null,
    removeItem: (key: string) => {
      map.delete(key);
    },
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
  } as Storage;
}

describe('createAndOpenArchitectSession', () => {
  beforeEach(() => {
    createSession.mockReset();
    createSession.mockResolvedValue({ id: 'sess-123', title: 'T' });
  });

  it('opens about:blank sync, creates an empty session, stashes the message, then navigates', async () => {
    const tab = { closed: false, location: { href: '' } };
    const openWindow = jest.fn().mockReturnValue(tab);
    const navigate = jest.fn();
    const storage = createMockStorage();

    await createAndOpenArchitectSession({
      title: 'Insights summary — Bot — 1M',
      initialMessage: 'Summarize insights\ntest results',
      openWindow,
      navigate,
      storage,
    });

    expect(openWindow).toHaveBeenCalledWith('about:blank', '_blank');
    // The message is NOT sent to the backend — that would start the turn
    // before the new tab connects. It is stashed for the tab to send itself.
    expect(createSession).toHaveBeenCalledWith({
      title: 'Insights summary — Bot — 1M',
    });
    expect(takePendingHandoffMessage('sess-123', storage)).toBe(
      'Summarize insights\ntest results'
    );
    expect(tab.location.href).toBe('/architect?session=sess-123');
    expect(navigate).not.toHaveBeenCalled();
  });

  it('falls back to same-tab navigation when popup is blocked', async () => {
    const openWindow = jest.fn().mockReturnValue(null);
    const navigate = jest.fn();
    const storage = createMockStorage();

    await createAndOpenArchitectSession({
      title: 'Title',
      initialMessage: 'Message',
      openWindow,
      navigate,
      storage,
    });

    expect(navigate).toHaveBeenCalledWith('/architect?session=sess-123');
    expect(takePendingHandoffMessage('sess-123', storage)).toBe('Message');
  });

  it('closes the placeholder tab if create fails', async () => {
    const tab = { closed: false, close: jest.fn(), location: { href: '' } };
    const openWindow = jest.fn().mockReturnValue(tab);
    createSession.mockRejectedValue(new Error('boom'));

    await expect(
      createAndOpenArchitectSession({
        title: 'Title',
        initialMessage: 'Message',
        openWindow,
        navigate: jest.fn(),
      })
    ).rejects.toThrow('boom');

    expect(tab.close).toHaveBeenCalled();
  });
});

describe('takePendingHandoffMessage', () => {
  it('is single-use: returns the message once then null', () => {
    const storage = createMockStorage();
    createAndOpenArchitectSessionStash(storage);

    expect(takePendingHandoffMessage('sess-1', storage)).toBe('hello');
    expect(takePendingHandoffMessage('sess-1', storage)).toBeNull();
  });

  it('returns null for an unknown session', () => {
    const storage = createMockStorage();
    expect(takePendingHandoffMessage('missing', storage)).toBeNull();
  });

  it('ignores an expired envelope', () => {
    const storage = createMockStorage();
    storage.setItem(
      'architect:pendingHandoff:sess-old',
      JSON.stringify({ message: 'stale', createdAt: 0 })
    );
    expect(takePendingHandoffMessage('sess-old', storage)).toBeNull();
  });
});

describe('peekPendingHandoffMessage / clearPendingHandoffMessage', () => {
  it('peek is non-destructive: repeated peeks return the same message', () => {
    const storage = createMockStorage();
    createAndOpenArchitectSessionStash(storage);

    expect(peekPendingHandoffMessage('sess-1', storage)).toBe('hello');
    expect(peekPendingHandoffMessage('sess-1', storage)).toBe('hello');
  });

  it('clear removes the entry so a later peek returns null', () => {
    const storage = createMockStorage();
    createAndOpenArchitectSessionStash(storage);

    expect(peekPendingHandoffMessage('sess-1', storage)).toBe('hello');
    clearPendingHandoffMessage('sess-1', storage);
    expect(peekPendingHandoffMessage('sess-1', storage)).toBeNull();
  });

  it('peek ignores an expired envelope', () => {
    const storage = createMockStorage();
    storage.setItem(
      'architect:pendingHandoff:sess-old',
      JSON.stringify({ message: 'stale', createdAt: 0 })
    );
    expect(peekPendingHandoffMessage('sess-old', storage)).toBeNull();
  });
});

function createAndOpenArchitectSessionStash(storage: Storage) {
  storage.setItem(
    'architect:pendingHandoff:sess-1',
    JSON.stringify({ message: 'hello', createdAt: Date.now() })
  );
}
