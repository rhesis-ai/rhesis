/**
 * next/server needs the WHATWG Request/Response globals, which the default
 * jsdom environment does not provide.
 *
 * @jest-environment node
 */
import { GET } from '@/app/api/architect-help/route';

const ENV_KEY = 'ARCHITECT_HELP_ARTICLE_URLS';

async function articleUrls(): Promise<string[]> {
  const response = await GET();
  const body = (await response.json()) as { articleUrls: string[] };
  return body.articleUrls;
}

describe('GET /api/architect-help', () => {
  const original = process.env[ENV_KEY];

  afterEach(() => {
    if (original === undefined) {
      delete process.env[ENV_KEY];
    } else {
      process.env[ENV_KEY] = original;
    }
  });

  it('returns an empty list when unset', async () => {
    delete process.env[ENV_KEY];
    await expect(articleUrls()).resolves.toEqual([]);
  });

  it('splits a comma-separated list and trims whitespace', async () => {
    process.env[ENV_KEY] =
      ' https://docs.rhesis.ai/docs/endpoints , https://docs.rhesis.ai/docs/concepts ';

    await expect(articleUrls()).resolves.toEqual([
      'https://docs.rhesis.ai/docs/endpoints',
      'https://docs.rhesis.ai/docs/concepts',
    ]);
  });

  it('caps the list at four URLs — one card row', async () => {
    process.env[ENV_KEY] = [1, 2, 3, 4, 5, 6]
      .map(n => `https://docs.rhesis.ai/docs/page-${n}`)
      .join(',');

    await expect(articleUrls()).resolves.toHaveLength(4);
  });

  it('drops hosts the og-metadata proxy would reject', async () => {
    process.env[ENV_KEY] =
      'https://docs.rhesis.ai/docs/endpoints,https://evil.example/docs,not-a-url';

    await expect(articleUrls()).resolves.toEqual([
      'https://docs.rhesis.ai/docs/endpoints',
    ]);
  });
});
