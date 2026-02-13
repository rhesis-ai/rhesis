import {
  shouldShowGitInfo,
  getGitInfo,
  getVersionInfo,
  formatVersionDisplay,
} from '../git-utils';

type MutableEnv = Record<string, string | undefined>;

describe('shouldShowGitInfo', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns true when FRONTEND_ENV is development', () => {
    process.env.FRONTEND_ENV = 'development';
    expect(shouldShowGitInfo()).toBe(true);
  });

  it('returns true when NODE_ENV is development', () => {
    delete (process.env as MutableEnv).FRONTEND_ENV;
    (process.env as MutableEnv).NODE_ENV = 'development';
    expect(shouldShowGitInfo()).toBe(true);
  });

  it('is case-insensitive', () => {
    process.env.FRONTEND_ENV = 'Development';
    expect(shouldShowGitInfo()).toBe(true);
  });

  it('returns false for production', () => {
    process.env.FRONTEND_ENV = 'production';
    (process.env as MutableEnv).NODE_ENV = 'production';
    expect(shouldShowGitInfo()).toBe(false);
  });

  it('returns false for staging', () => {
    process.env.FRONTEND_ENV = 'staging';
    (process.env as MutableEnv).NODE_ENV = 'production';
    expect(shouldShowGitInfo()).toBe(false);
  });
});

describe('getGitInfo', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns branch and commit from env vars', () => {
    process.env.GIT_BRANCH = 'main';
    process.env.GIT_COMMIT = 'abc1234';
    const info = getGitInfo();
    expect(info.branch).toBe('main');
    expect(info.commit).toBe('abc1234');
  });

  it('returns undefined when env vars are not set', () => {
    delete (process.env as MutableEnv).GIT_BRANCH;
    delete (process.env as MutableEnv).GIT_COMMIT;
    const info = getGitInfo();
    expect(info.branch).toBeUndefined();
    expect(info.commit).toBeUndefined();
  });
});

describe('getVersionInfo', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns version from APP_VERSION', () => {
    process.env.APP_VERSION = '1.2.3';
    process.env.FRONTEND_ENV = 'production';
    const info = getVersionInfo();
    expect(info.version).toBe('1.2.3');
  });

  it('defaults to 0.0.0 when APP_VERSION is not set', () => {
    delete (process.env as MutableEnv).APP_VERSION;
    process.env.FRONTEND_ENV = 'production';
    const info = getVersionInfo();
    expect(info.version).toBe('0.0.0');
  });

  it('includes git info in development', () => {
    process.env.APP_VERSION = '1.0.0';
    process.env.FRONTEND_ENV = 'development';
    process.env.GIT_BRANCH = 'feature/test';
    process.env.GIT_COMMIT = 'def5678';
    const info = getVersionInfo();
    expect(info.version).toBe('1.0.0');
    expect(info.branch).toBe('feature/test');
    expect(info.commit).toBe('def5678');
  });

  it('excludes git info in production', () => {
    process.env.APP_VERSION = '1.0.0';
    process.env.FRONTEND_ENV = 'production';
    (process.env as MutableEnv).NODE_ENV = 'production';
    process.env.GIT_BRANCH = 'main';
    process.env.GIT_COMMIT = 'abc1234';
    const info = getVersionInfo();
    expect(info.branch).toBeUndefined();
    expect(info.commit).toBeUndefined();
  });
});

describe('formatVersionDisplay', () => {
  it('formats version only', () => {
    expect(formatVersionDisplay({ version: '1.2.3' })).toBe('v1.2.3');
  });

  it('formats version with custom prefix', () => {
    expect(formatVersionDisplay({ version: '1.2.3' }, 'V')).toBe('V1.2.3');
  });

  it('formats version with branch', () => {
    expect(formatVersionDisplay({ version: '1.0.0', branch: 'main' })).toBe(
      'v1.0.0 (main)'
    );
  });

  it('formats version with commit', () => {
    expect(formatVersionDisplay({ version: '1.0.0', commit: 'abc1234' })).toBe(
      'v1.0.0 (abc1234)'
    );
  });

  it('formats version with branch and commit', () => {
    expect(
      formatVersionDisplay({
        version: '1.0.0',
        branch: 'main',
        commit: 'abc1234',
      })
    ).toBe('v1.0.0 (main@abc1234)');
  });

  it('formats with empty prefix', () => {
    expect(formatVersionDisplay({ version: '1.0.0' }, '')).toBe('1.0.0');
  });
});
