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

function checkRequired(errors: string[]): void {
  if (!read('API_BASE_URL')) {
    errors.push('API_BASE_URL is required but not set');
  }

  for (const name of ['API_BASE_URL', 'BACKEND_URL', 'FRONTEND_URL']) {
    const value = read(name);
    if (value && !isHttpUrl(value)) {
      errors.push(`${name} is not an http(s) URL: "${value}"`);
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

  for (const url of readList('ARCHITECT_HELP_ARTICLE_URLS')) {
    if (!isAllowedArticleUrl(url)) {
      warnings.push(
        `ARCHITECT_HELP_ARTICLE_URLS entry is not a docs.rhesis.ai page, so it is dropped: "${url}"`
      );
    }
  }

  for (const prefix of Object.values(EMPTY_STATE_ENV_PREFIX)) {
    const videoName = `${prefix}_EMPTY_STATE_VIDEO_URL`;
    const video = read(videoName);
    if (video && !parseYouTubeVideoId(video)) {
      warnings.push(
        `${videoName} is not a YouTube link, so no video shows: "${video}"`
      );
    }

    const articlesName = `${prefix}_EMPTY_STATE_ARTICLE_URLS`;
    for (const url of readList(articlesName)) {
      if (!isAllowedArticleUrl(url)) {
        warnings.push(
          `${articlesName} entry is not a docs.rhesis.ai page, so its card shows only the bare link: "${url}"`
        );
      }
    }
  }

  const supportEmail = read('SUPPORT_EMAIL');
  if (supportEmail && !supportEmail.includes('@')) {
    warnings.push(`SUPPORT_EMAIL is not an email address: "${supportEmail}"`);
  }
}

/** Branding is checked where it is parsed, in `config/branding.ts`. */
export function checkEnv(): EnvProblems {
  const problems: EnvProblems = { errors: [], warnings: [] };
  checkRequired(problems.errors);
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
