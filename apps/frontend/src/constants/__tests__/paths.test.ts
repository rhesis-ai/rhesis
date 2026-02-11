import { isPublicPath, isOnboardingPath, PUBLIC_PATHS } from '../paths';

describe('isPublicPath', () => {
  it('matches exact public paths', () => {
    expect(isPublicPath('/')).toBe(true);
    expect(isPublicPath('/auth/signin')).toBe(true);
    expect(isPublicPath('/auth/signup')).toBe(true);
    expect(isPublicPath('/auth/signout')).toBe(true);
    expect(isPublicPath('/auth/callback')).toBe(true);
    expect(isPublicPath('/auth/forgot-password')).toBe(true);
    expect(isPublicPath('/auth/reset-password')).toBe(true);
    expect(isPublicPath('/auth/verify-email')).toBe(true);
    expect(isPublicPath('/api/warmup')).toBe(true);
  });

  it('matches static asset paths by prefix', () => {
    expect(isPublicPath('/_next/static/chunk.js')).toBe(true);
    expect(isPublicPath('/images/logo.png')).toBe(true);
    expect(isPublicPath('/assets/styles.css')).toBe(true);
    expect(isPublicPath('/fonts/Inter.woff2')).toBe(true);
  });

  it('matches static files by extension', () => {
    expect(isPublicPath('/favicon.ico')).toBe(true);
    expect(isPublicPath('/logo.png')).toBe(true);
    expect(isPublicPath('/style.css')).toBe(true);
    expect(isPublicPath('/bundle.js')).toBe(true);
    expect(isPublicPath('/font.woff2')).toBe(true);
    expect(isPublicPath('/image.svg')).toBe(true);
  });

  it('rejects protected paths', () => {
    expect(isPublicPath('/dashboard')).toBe(false);
    expect(isPublicPath('/projects')).toBe(false);
    expect(isPublicPath('/test-runs')).toBe(false);
    expect(isPublicPath('/settings')).toBe(false);
    expect(isPublicPath('/tasks')).toBe(false);
  });

  it('rejects paths that look similar but are not public', () => {
    expect(isPublicPath('/auth-custom')).toBe(false);
    expect(isPublicPath('/api/v1/tests')).toBe(false);
  });

  it('has all expected public paths in the constant', () => {
    expect(PUBLIC_PATHS).toContain('/');
    expect(PUBLIC_PATHS).toContain('/auth/signin');
    expect(PUBLIC_PATHS).toContain('/auth/signout');
    expect(PUBLIC_PATHS).toContain('/api/auth');
  });
});

describe('isOnboardingPath', () => {
  it('matches exact onboarding path', () => {
    expect(isOnboardingPath('/onboarding')).toBe(true);
  });

  it('matches onboarding sub-paths', () => {
    expect(isOnboardingPath('/onboarding/step-1')).toBe(true);
    expect(isOnboardingPath('/onboarding/complete')).toBe(true);
  });

  it('rejects non-onboarding paths', () => {
    expect(isOnboardingPath('/dashboard')).toBe(false);
    expect(isOnboardingPath('/')).toBe(false);
    expect(isOnboardingPath('/onboarding-extra')).toBe(false);
  });
});
