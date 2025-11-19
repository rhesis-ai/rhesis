/**
 * Quick Start mode detection utility for frontend.
 *
 * Quick Start is ONLY enabled when QUICK_START=true AND all signals confirm QUICK START MODE.
 */

/**
 * Determine if QUICK START MODE should be enabled.
 *
 * Quick Start is ONLY enabled when ALL of the following conditions are met:
 * 1. QUICK_START environment variable is explicitly set to 'true'
 * 2. Hostname/domain does NOT indicate cloud deployment
 * 3. Google Cloud Run domains are NOT detected
 *
 * This is a fail-secure function: if ANY signal indicates cloud deployment,
 * it returns false. Default is false for safety.
 *
 * @param hostname - Optional hostname to check (defaults to window.location.hostname)
 * @returns True ONLY if all signals confirm QUICK START MODE, False otherwise
 *
 * @example
 * ```typescript
 * if (isQuickStartEnabled()) {
 *   // Show Quick Start login button
 * }
 * ```
 */
export function isQuickStartEnabled(hostname?: string): boolean {
  // 1. Check QUICK_START environment variable (default: false for safety)
  // In Next.js, check both NEXT_PUBLIC_QUICK_START (build-time) and QUICK_START (runtime)
  const quickStartEnv =
    process.env.NEXT_PUBLIC_QUICK_START === 'true' ||
    process.env.QUICK_START === 'true';

  if (!quickStartEnv) {
    console.debug("QUICK START MODE disabled: QUICK_START not set to 'true'");
    return false;
  }

  console.debug(
    "QUICK START MODE environment variable set to 'true', validating deployment signals..."
  );

  // 2. HOSTNAME/DOMAIN CHECKS - Fail if cloud domain detected
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
  console.info(
    ' QUICK START MODE enabled - all signals confirm QUICK START MODE'
  );
  return true;
}
