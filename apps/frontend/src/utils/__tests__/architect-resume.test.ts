import {
  ARCHITECT_RESUME_TTL_MS,
  clearResumeHint,
  pickResumableSessionId,
  readResumeHint,
  writeResumeHint,
} from '../architect-resume';

const PROJECT_ID = 'project-1';
const SESSION_ID = 'session-abc';

beforeEach(() => {
  sessionStorage.clear();
  jest.useFakeTimers();
  jest.setSystemTime(new Date('2026-07-09T12:00:00.000Z'));
});

afterEach(() => {
  jest.useRealTimers();
});

describe('architect-resume', () => {
  it('writes and reads a resume hint', () => {
    writeResumeHint(PROJECT_ID, SESSION_ID);

    expect(readResumeHint(PROJECT_ID)).toEqual({
      sessionId: SESSION_ID,
      lastActiveAt: Date.now(),
    });
  });

  it('returns null when hint is expired', () => {
    writeResumeHint(PROJECT_ID, SESSION_ID);
    jest.advanceTimersByTime(ARCHITECT_RESUME_TTL_MS + 1);

    expect(readResumeHint(PROJECT_ID)).toBeNull();
    expect(sessionStorage.getItem(`architect:resume:${PROJECT_ID}`)).toBeNull();
  });

  it('clears invalid stored JSON', () => {
    sessionStorage.setItem(
      `architect:resume:${PROJECT_ID}`,
      '{not valid json'
    );

    expect(readResumeHint(PROJECT_ID)).toBeNull();
    expect(sessionStorage.getItem(`architect:resume:${PROJECT_ID}`)).toBeNull();
  });

  it('pickResumableSessionId returns hint when session exists', () => {
    writeResumeHint(PROJECT_ID, SESSION_ID);

    expect(
      pickResumableSessionId(PROJECT_ID, [{ id: SESSION_ID }, { id: 'other' }])
    ).toBe(SESSION_ID);
  });

  it('pickResumableSessionId clears hint when session is missing', () => {
    writeResumeHint(PROJECT_ID, SESSION_ID);

    expect(pickResumableSessionId(PROJECT_ID, [{ id: 'other' }])).toBeNull();
    expect(readResumeHint(PROJECT_ID)).toBeNull();
  });

  it('clearResumeHint removes stored hint', () => {
    writeResumeHint(PROJECT_ID, SESSION_ID);
    clearResumeHint(PROJECT_ID);

    expect(readResumeHint(PROJECT_ID)).toBeNull();
  });

  it('scopes hints per project', () => {
    writeResumeHint('project-a', 'session-a');
    writeResumeHint('project-b', 'session-b');

    expect(readResumeHint('project-a')?.sessionId).toBe('session-a');
    expect(readResumeHint('project-b')?.sessionId).toBe('session-b');
  });
});
