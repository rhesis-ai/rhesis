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
  // 1. Check QUICK_START environment variable (default: false for safety).
  //
  // The value is captured into a string variable before comparison so the
  // build-time placeholder (`__NEXT_PUBLIC_QUICK_START__`) survives SWC
  // constant folding and can be substituted at container start by
  // scripts/replace-runtime-env.sh. Direct `=== 'true'` comparison gets
  // folded to a static `false` and removes the placeholder from the bundle.
  const raw = process.env.NEXT_PUBLIC_QUICK_START ?? '';
  const quickStartEnv = String(raw).trim().toLowerCase() === 'true';

  if (!quickStartEnv) {
    return false;
  }

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
  return true;
}
