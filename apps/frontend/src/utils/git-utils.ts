/**
 * Utility functions for getting git information in the frontend.
 */

export interface GitInfo {
  branch?: string;
  commit?: string;
}

export interface VersionInfo {
  version: string;
  branch?: string;
  commit?: string;
}

/**
 * Determine if git information should be shown based on environment.
 * Returns true only for development environments.
 */
export function shouldShowGitInfo(): boolean {
  const frontendEnv = process.env.FRONTEND_ENV?.toLowerCase();
  const nodeEnv = process.env.NODE_ENV?.toLowerCase();

  // Only show git info in development (not in staging or production)
  return frontendEnv === 'development' || nodeEnv === 'development';
}

/**
 * Get git information from build-time environment variables.
 * These need to be set during the build process.
 */
export function getGitInfo(): GitInfo {
  return {
    branch: process.env.GIT_BRANCH,
    commit: process.env.GIT_COMMIT,
  };
}

/**
 * Get complete version information including git details when appropriate.
 */
export function getVersionInfo(): VersionInfo {
  const version = process.env.APP_VERSION || '0.0.0';
  const versionInfo: VersionInfo = { version };

  if (shouldShowGitInfo()) {
    const gitInfo = getGitInfo();
    if (gitInfo.branch) {
      versionInfo.branch = gitInfo.branch;
    }
    if (gitInfo.commit) {
      versionInfo.commit = gitInfo.commit;
    }
  }

  return versionInfo;
}

/**
 * Format version information for display.
 */
export function formatVersionDisplay(
  versionInfo: VersionInfo,
  prefix: string = 'v'
): string {
  let display = `${prefix}${versionInfo.version}`;

  if (versionInfo.branch || versionInfo.commit) {
    const gitParts: string[] = [];
    if (versionInfo.branch) {
      gitParts.push(versionInfo.branch);
    }
    if (versionInfo.commit) {
      gitParts.push(versionInfo.commit);
    }
    display += ` (${gitParts.join('@')})`;
  }

  return display;
}
