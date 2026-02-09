// Define onboarding path constant
export const ONBOARDING_PATH = '/onboarding';

export const PUBLIC_PATHS = [
  '/', // Root path is public
  '/public',
  '/auth',
  '/api/auth',
  '/api/warmup', // Allow warmup endpoint
  '/_next',
  '/rhesis-favicon.ico',
  '/rhesis-logo.png',
  '/rhesis-icon.png',
  '/rhesis-logo-white.png',
  '/background.png',
  '/rhesis-favicon.png',
  '/avatar.png',
  '/auth0-lock.js',
  '/auth0-lock.css',
  '/auth/signin',
  '/auth/signup',
  '/auth/callback',
  '/auth/error',
  '/auth/verify-request',
  '/auth/signout',
  '/auth/session',
  '/auth/register',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/magic-link',
] as const;

export function isPublicPath(path: string): boolean {
  // Check exact matches
  if (PUBLIC_PATHS.includes(path as any)) {
    return true;
  }

  // Check static asset paths
  const staticPaths = ['/_next/', '/images/', '/assets/', '/fonts/'];
  if (staticPaths.some(prefix => path.startsWith(prefix))) {
    return true;
  }

  // Check file extensions for common static files
  const staticExtensions = [
    '.ico',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.svg',
    '.css',
    '.js',
    '.ttf',
    '.woff',
    '.woff2',
    '.eot',
    '.otf',
  ];
  if (staticExtensions.some(ext => path.endsWith(ext))) {
    return true;
  }

  return false;
}

// Check if path is the onboarding path
export const isOnboardingPath = (pathname: string): boolean =>
  pathname === ONBOARDING_PATH || pathname.startsWith(`${ONBOARDING_PATH}/`);
