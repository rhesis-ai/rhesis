import { isAllowedOgMetadataUrl } from '@/app/api/og-metadata/og-metadata-utils';
import type { EntityEmptyStateKey } from '@/constants/entity-empty-state-types';

/**
 * Every deployment-config env var the frontend reads, declared once.
 *
 * One image serves every environment, so none of these are `NEXT_PUBLIC_*`:
 * that prefix inlines a value into the client bundle at `next build`, and the
 * value on the pod is then ignored. Server code reads them at request time
 * with `serverEnv()`. The part the browser needs is `PublicEnv`: the root
 * layout writes it into `window.__ENV__`, and `publicEnv()` reads it there.
 * `config/enforce-env.ts` checks the values at server startup.
 *
 * Not here: NextAuth's own vars (`NEXTAUTH_SECRET`, `AUTH_URL`,
 * `NEXTAUTH_URL`), Next.js's (`NODE_ENV`, `NEXT_RUNTIME`), and build facts
 * baked by `next.config.mjs` (`APP_VERSION`, `NEXT_PUBLIC_GIT_*`).
 */

export const DEFAULT_SUPPORT_EMAIL = 'hello@rhesis.ai';
const DEFAULT_BACKEND_URL = 'http://backend:8080';

/** One card row is all a help section shows. */
const MAX_ARTICLE_URLS = 4;

/** Env var prefix per entity: `<PREFIX>_EMPTY_STATE_VIDEO_URL` / `_ARTICLE_URLS`. */
export const EMPTY_STATE_ENV_PREFIX: Record<EntityEmptyStateKey, string> = {
  projects: 'PROJECTS',
  tests: 'TESTS',
  'test-sets': 'TEST_SETS',
  'test-runs': 'TEST_RUNS',
  endpoints: 'ENDPOINTS',
  requirements: 'REQUIREMENTS',
  metrics: 'METRICS',
  experiments: 'EXPERIMENTS',
};

export interface EmptyStateEnv {
  videoUrl?: string;
  articleUrls: string[];
}

/** Sent to the browser in the page HTML, so never put a secret here. */
export interface PublicEnv {
  /** `API_BASE_URL`: public backend origin for the browser's `/auth/*` calls. */
  apiBaseUrl?: string;
  /** `FRONTEND_ENV`: development, staging or production. */
  environment?: string;
  supportEmail: string;
  /** Docs pages for the Architect welcome help cards. */
  architectHelpArticleUrls: string[];
  emptyStates: Partial<Record<EntityEmptyStateKey, EmptyStateEnv>>;
}

export interface ServerEnv {
  /** `BACKEND_URL`: in-cluster backend origin for server-side calls. */
  backendUrl: string;
  /** `FRONTEND_URL`: public frontend origin; `https://` enables secure cookies. */
  frontendUrl?: string;
  onboardingVideoUrl?: string;
  /** Raw `BRAND_*` values; `config/branding.ts` validates and normalizes them. */
  brand: {
    primaryColor?: string;
    secondaryColor?: string;
    faviconUrl?: string;
    productName?: string;
    fontFamily?: string;
    fontBaseUrl?: string;
  };
}

export function read(name: string): string | undefined {
  return process.env[name]?.trim() || undefined;
}

export function readList(name: string): string[] {
  return (read(name) ?? '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean);
}

/** Server only. Reads the container environment on every call. */
export function serverEnv(): ServerEnv {
  return {
    backendUrl: read('BACKEND_URL') ?? DEFAULT_BACKEND_URL,
    frontendUrl: read('FRONTEND_URL'),
    onboardingVideoUrl: read('ONBOARDING_VIDEO_URL'),
    brand: {
      primaryColor: read('BRAND_PRIMARY_COLOR'),
      secondaryColor: read('BRAND_SECONDARY_COLOR'),
      faviconUrl: read('BRAND_FAVICON_URL'),
      productName: read('BRAND_PRODUCT_NAME'),
      fontFamily: read('BRAND_FONT_FAMILY'),
      fontBaseUrl: read('BRAND_FONT_BASE_URL'),
    },
  };
}

// Same allowlist /api/og-metadata enforces, so a misconfigured host never
// becomes a card whose metadata fetch is guaranteed to 403.
export function isAllowedArticleUrl(value: string): boolean {
  try {
    return isAllowedOgMetadataUrl(new URL(value));
  } catch {
    return false;
  }
}

function readEmptyStates(): PublicEnv['emptyStates'] {
  const emptyStates: PublicEnv['emptyStates'] = {};
  for (const [key, prefix] of Object.entries(EMPTY_STATE_ENV_PREFIX)) {
    const videoUrl = read(`${prefix}_EMPTY_STATE_VIDEO_URL`);
    const articleUrls = readList(`${prefix}_EMPTY_STATE_ARTICLE_URLS`).slice(
      0,
      MAX_ARTICLE_URLS
    );
    if (videoUrl || articleUrls.length > 0) {
      emptyStates[key as EntityEmptyStateKey] = { videoUrl, articleUrls };
    }
  }
  return emptyStates;
}

const UNSET_PUBLIC_ENV: PublicEnv = {
  supportEmail: DEFAULT_SUPPORT_EMAIL,
  architectHelpArticleUrls: [],
  emptyStates: {},
};

/** Server only: builds the browser's copy from the container environment. */
export function readPublicEnv(): PublicEnv {
  return {
    apiBaseUrl: read('API_BASE_URL'),
    environment: read('FRONTEND_ENV'),
    supportEmail: read('SUPPORT_EMAIL') ?? UNSET_PUBLIC_ENV.supportEmail,
    architectHelpArticleUrls: readList('ARCHITECT_HELP_ARTICLE_URLS')
      .filter(isAllowedArticleUrl)
      .slice(0, MAX_ARTICLE_URLS),
    emptyStates: readEmptyStates(),
  };
}

/**
 * Safe in server and client components. The server render reads the
 * environment and the browser reads the root layout's copy of the same values,
 * so both render the same markup and hydration agrees.
 */
export function publicEnv(): PublicEnv {
  if (typeof window === 'undefined') return readPublicEnv();
  return { ...UNSET_PUBLIC_ENV, ...window.__ENV__ };
}
