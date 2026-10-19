import type { EntityEmptyStateKey } from '@/constants/entity-empty-state-types';

/**
 * Per-deployment UI content (support address, empty-state media) that the
 * client needs.
 *
 * These are plain env vars, deliberately without the `NEXT_PUBLIC_` prefix:
 * that prefix inlines a value into the client bundle at build time, so changing
 * it would mean rebuilding the image. They are read here at request time and
 * reach the browser through `window.__ENV__`, which the root layout fills —
 * the same route `API_BASE_URL` and the deployment branding take.
 */

export const DEFAULT_SUPPORT_EMAIL = 'hello@rhesis.ai';

export interface EmptyStateEnvSources {
  videoUrl?: string;
  /** Comma-separated; parsed by `parseCommaSeparatedUrls`. */
  articleUrls?: string;
}

export interface RuntimeContentEnv {
  supportEmail: string;
  emptyStates: Partial<Record<EntityEmptyStateKey, EmptyStateEnvSources>>;
}

/** Env var prefix per entity: `<PREFIX>_EMPTY_STATE_VIDEO_URL` / `_ARTICLE_URLS`. */
const EMPTY_STATE_ENV_PREFIX: Record<EntityEmptyStateKey, string> = {
  projects: 'PROJECTS',
  tests: 'TESTS',
  'test-sets': 'TEST_SETS',
  'test-runs': 'TEST_RUNS',
  endpoints: 'ENDPOINTS',
  requirements: 'REQUIREMENTS',
  metrics: 'METRICS',
  experiments: 'EXPERIMENTS',
};

function readEnv(name: string): string | undefined {
  return process.env[name]?.trim() || undefined;
}

/** Server only: reads the container environment. */
export function readRuntimeContentEnv(): RuntimeContentEnv {
  const emptyStates: RuntimeContentEnv['emptyStates'] = {};
  for (const [key, prefix] of Object.entries(EMPTY_STATE_ENV_PREFIX)) {
    const videoUrl = readEnv(`${prefix}_EMPTY_STATE_VIDEO_URL`);
    const articleUrls = readEnv(`${prefix}_EMPTY_STATE_ARTICLE_URLS`);
    if (videoUrl || articleUrls) {
      emptyStates[key as EntityEmptyStateKey] = { videoUrl, articleUrls };
    }
  }

  return {
    supportEmail: readEnv('SUPPORT_EMAIL') ?? DEFAULT_SUPPORT_EMAIL,
    emptyStates,
  };
}

/**
 * Safe in server and client components. The server render reads the
 * environment directly and the browser reads the root layout's copy of it, so
 * both render the same markup and hydration agrees.
 */
export function getRuntimeContentEnv(): RuntimeContentEnv {
  if (typeof window === 'undefined') return readRuntimeContentEnv();
  return (
    window.__ENV__?.content ?? {
      supportEmail: DEFAULT_SUPPORT_EMAIL,
      emptyStates: {},
    }
  );
}
