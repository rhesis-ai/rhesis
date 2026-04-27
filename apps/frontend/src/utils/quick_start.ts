/**
 * Quick Start mode detection utility for frontend.
 *
 * The backend owns the local-login gate. The frontend only checks whether the
 * current host is safe before attempting backend local-login.
 */
export function isQuickStartHostAllowed(hostname?: string): boolean {
  const checkHostname =
    hostname || (typeof window !== 'undefined' ? window.location.hostname : '');
  if (checkHostname) {
    const hostnameLower = checkHostname.toLowerCase();

    // Check for Rhesis cloud domains (any domain containing rhesis.ai)
    if (hostnameLower.includes('rhesis.ai')) {
      console.warn(
        ` QUICK START MODE disabled: Cloud hostname detected (${checkHostname})`
      );
      return false;
    }

    // Google Cloud Run domains
    const cloudRunDomains = ['.run.app', '.cloudrun.dev', '.appspot.com'];

    // Check for Cloud Run domains
    for (const cloudDomain of cloudRunDomains) {
      if (hostnameLower.includes(cloudDomain)) {
        console.warn(
          ` QUICK START MODE disabled: Cloud Run domain detected (${checkHostname})`
        );
        return false;
      }
    }
  }

  // All checks passed - QUICK START MODE is enabled
  return true;
}
