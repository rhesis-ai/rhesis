export const PROTECTED_PATHS = {
  SUPERUSER: [
    '/projects-legacy',
    '/projects',
    '/organizations/team',
    '/organizations/risks',
    '/organizations/knowledge',
    '/runs',
    '/metrics',
    '/reports',
    '/integrations'
    // Add other superuser-only paths here
  ],
  // You can add other path categories here
  // Example:
  // ADMIN: ['/admin', '/settings'],
  // PREMIUM: ['/premium-features']
} as const;

// Define onboarding path constant
export const ONBOARDING_PATH = '/onboarding';

export const PUBLIC_PATHS = [
  '/',
  '/public',
  '/auth',
  '/api/auth',
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
] as const;

// Helper functions if needed
export const isSuperuserPath = (path: string): boolean => 
  PROTECTED_PATHS.SUPERUSER.some(protectedPath => 
    path.startsWith(protectedPath)
  );

export function isPublicPath(path: string): boolean {
  // Check exact matches
  if (PUBLIC_PATHS.includes(path as any)) {
    return true;
  }
  
  // Check static asset paths
  const staticPaths = ['/_next/', '/images/', '/assets/'];
  if (staticPaths.some(prefix => path.startsWith(prefix))) {
    return true;
  }
  
  // Check file extensions for common static files
  const staticExtensions = ['.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js'];
  if (staticExtensions.some(ext => path.endsWith(ext))) {
    return true;
  }
  
  return false;
}

// Check if path is the onboarding path
export const isOnboardingPath = (pathname: string): boolean =>
  pathname === ONBOARDING_PATH || pathname.startsWith(`${ONBOARDING_PATH}/`); 