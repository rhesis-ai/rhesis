import {
  EMPTY_STATE_ENV_PREFIX,
  isAllowedArticleUrl,
  read,
  readList,
} from '@/config/runtime-config';
import {
  getOnboardingVideoEmbedUrl,
  parseYouTubeVideoId,
} from '@/utils/onboarding-video';

export interface EnvProblems {
  /** The app cannot work: sign-in or backend calls would break. */
  errors: string[];
  /** Optional content that will not show the way it was meant to. */
  warnings: string[];
}

function isHttpUrl(value: string): boolean {
  try {
    const { protocol } = new URL(value);
    return protocol === 'http:' || protocol === 'https:';
  } catch {
    return false;
  }
}

function isWsUrl(value: string): boolean {
  if (value.startsWith('/')) return true;
  try {
    const { protocol } = new URL(value);
    return protocol === 'ws:' || protocol === 'wss:';
  } catch {
    return false;
  }
}

function checkRequired(errors: string[]): void {
  for (const name of ['BACKEND_URL', 'FRONTEND_URL']) {
    const value = read(name);
    if (value && !isHttpUrl(value)) {
      errors.push(`${name} is not an http(s) URL: "${value}"`);
    }
  }

  const wsUrl = read('WS_URL');
  if (wsUrl && !isWsUrl(wsUrl)) {
    errors.push(`WS_URL is not a path or a ws(s) URL: "${wsUrl}"`);
  }
}

// BACKEND_URL is the backend's internal address. Pointed at a public host it
// still works, but every call leaves and re-enters through the proxy, so the
// backend sees the proxy's IP: sign-ins share one rate limit and the audit log
// records the proxy. Same host *and* port as FRONTEND_URL means the app itself
// (localhost:3000 vs localhost:8080 in local dev is fine).
function checkBackendUrlIsInternal(warnings: string[]): void {
  const backend = read('BACKEND_URL');
  if (!backend || !isHttpUrl(backend)) return;
  const backendUrl = new URL(backend);
  const frontend = read('FRONTEND_URL');
  const fix =
    "Set it to the backend's internal address, such as http://backend:8080, or leave it unset";

  if (
    frontend &&
    isHttpUrl(frontend) &&
    new URL(frontend).host === backendUrl.host
  ) {
    warnings.push(
      `BACKEND_URL points at the app's own address (${backendUrl.host}). ${fix}.`
    );
  } else if (backendUrl.protocol === 'https:') {
    warnings.push(
      `BACKEND_URL uses https (${backend}), which usually means the public API host. ${fix}, so the backend sees each user's IP.`
    );
  }
}

function checkArticleUrls(name: string, warnings: string[]): void {
  for (const url of readList(name)) {
    if (!isAllowedArticleUrl(url)) {
      warnings.push(
        `${name} entry is not a docs.rhesis.ai page, so it is dropped: "${url}"`
      );
    }
  }
}

// Each warning matches what the UI does with the value, so a check that passes
// means the content really shows.
function checkContent(warnings: string[]): void {
  const onboardingVideo = read('ONBOARDING_VIDEO_URL');
  if (onboardingVideo && !getOnboardingVideoEmbedUrl(onboardingVideo)) {
    warnings.push(
      `ONBOARDING_VIDEO_URL is not a YouTube or Vimeo link, so no video shows: "${onboardingVideo}"`
    );
  }

  for (const prefix of Object.values(EMPTY_STATE_ENV_PREFIX)) {
    const videoName = `${prefix}_EMPTY_STATE_VIDEO_URL`;
    const video = read(videoName);
    if (video && !parseYouTubeVideoId(video)) {
      warnings.push(
        `${videoName} is not a YouTube link, so no video shows: "${video}"`
      );
    }

    checkArticleUrls(`${prefix}_EMPTY_STATE_ARTICLE_URLS`, warnings);
  }
  checkArticleUrls('ARCHITECT_HELP_ARTICLE_URLS', warnings);

  const supportEmail = read('SUPPORT_EMAIL');
  if (supportEmail && !supportEmail.includes('@')) {
    warnings.push(`SUPPORT_EMAIL is not an email address: "${supportEmail}"`);
  }
}

/** Branding is checked where it is parsed, in `config/branding.ts`. */
export function checkEnv(): EnvProblems {
  const problems: EnvProblems = { errors: [], warnings: [] };
  checkRequired(problems.errors);
  checkBackendUrlIsInternal(problems.warnings);
  checkContent(problems.warnings);
  return problems;
}

/**
 * Runs at startup from `instrumentation.ts`. Logs every problem; in production
 * an error also exits, so a bad rollout fails its pods and the old ones keep
 * serving. A warning never stops the app: losing a help card is not worth an
 * outage.
 */
export function enforceEnv(): void {
  const { errors, warnings } = checkEnv();
  for (const warning of warnings) console.warn(`[env] ${warning}`);
  for (const error of errors) console.error(`[env] ${error}`);
  if (errors.length > 0 && process.env.NODE_ENV === 'production') {
    process.exit(1);
  }
}
