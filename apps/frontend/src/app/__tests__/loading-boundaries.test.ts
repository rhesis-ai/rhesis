import fs from 'fs';
import path from 'path';

/**
 * A `loading.tsx` is the fallback for every route below it that has none of
 * its own. A directory's loading view draws that directory's real title, so a
 * page under it (a detail page, a create form) must bring its own fallback, or
 * it briefly shows the directory's header instead of its own.
 */

const PROTECTED = path.join(__dirname, '..', '(protected)');

/** Loading views that draw a directory page's own header. */
function drawsDirectoryHeader(loadingFile: string): boolean {
  const source = fs.readFileSync(loadingFile, 'utf8');
  return /header=\{PAGE_HEADERS\.\w+\}|\{\.\.\.PAGE_HEADERS\.\w+\}|PAGE_HEADERS\.models/.test(
    source
  );
}

function pageDirs(dir: string): string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (entry.name === '__tests__' || entry.name === 'components') continue;
    const child = path.join(dir, entry.name);
    if (fs.existsSync(path.join(child, 'page.tsx'))) found.push(child);
    found.push(...pageDirs(child));
  }
  return found;
}

function nearestLoading(dir: string): string | null {
  for (let cur = dir; cur.startsWith(PROTECTED); cur = path.dirname(cur)) {
    const candidate = path.join(cur, 'loading.tsx');
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

describe('route loading boundaries', () => {
  it('never shows a directory header in place of a page below it', () => {
    const borrowed = pageDirs(PROTECTED)
      .map(dir => ({ dir, loading: nearestLoading(dir) }))
      .filter(
        ({ dir, loading }) =>
          loading !== null &&
          path.dirname(loading) !== dir &&
          drawsDirectoryHeader(loading)
      )
      .map(({ dir, loading }) =>
        [
          path.relative(PROTECTED, dir),
          path.relative(PROTECTED, loading!),
        ].join(' <- ')
      );

    expect(borrowed).toEqual([]);
  });
});
