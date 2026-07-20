import { createAndOpenArchitectSession } from '../architect-handoff';

const createSession = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getArchitectClient: () => ({
      createSession,
    }),
  })),
}));

describe('createAndOpenArchitectSession', () => {
  beforeEach(() => {
    createSession.mockReset();
    createSession.mockResolvedValue({ id: 'sess-123', title: 'T' });
  });

  it('opens about:blank sync, creates session with initial_message, then navigates', async () => {
    const tab = { closed: false, location: { href: '' } };
    const openWindow = jest.fn().mockReturnValue(tab);
    const navigate = jest.fn();

    await createAndOpenArchitectSession({
      sessionToken: 'token',
      title: 'Insights summary — Bot — 1M',
      initialMessage: 'Summarize insights\ntest results',
      openWindow,
      navigate,
    });

    expect(openWindow).toHaveBeenCalledWith('about:blank', '_blank');
    expect(createSession).toHaveBeenCalledWith({
      title: 'Insights summary — Bot — 1M',
      initial_message: 'Summarize insights\ntest results',
    });
    expect(tab.location.href).toBe('/architect?session=sess-123');
    expect(navigate).not.toHaveBeenCalled();
  });

  it('falls back to same-tab navigation when popup is blocked', async () => {
    const openWindow = jest.fn().mockReturnValue(null);
    const navigate = jest.fn();

    await createAndOpenArchitectSession({
      sessionToken: 'token',
      title: 'Title',
      initialMessage: 'Message',
      openWindow,
      navigate,
    });

    expect(navigate).toHaveBeenCalledWith('/architect?session=sess-123');
  });

  it('closes the placeholder tab if create fails', async () => {
    const tab = { closed: false, close: jest.fn(), location: { href: '' } };
    const openWindow = jest.fn().mockReturnValue(tab);
    createSession.mockRejectedValue(new Error('boom'));

    await expect(
      createAndOpenArchitectSession({
        sessionToken: 'token',
        title: 'Title',
        initialMessage: 'Message',
        openWindow,
        navigate: jest.fn(),
      })
    ).rejects.toThrow('boom');

    expect(tab.close).toHaveBeenCalled();
  });
});
