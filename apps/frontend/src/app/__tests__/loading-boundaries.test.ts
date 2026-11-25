import fs from 'fs';
import path from 'path';

/**
 * A `loading.tsx` is the fallback for every route below it, and Next.js shows
 * the outermost one a navigation enters: opening a detail page from another
 * section shows the section's own loading view first, even when the detail
 * page has one of its own. A directory's loading view draws that directory's
 * real title, so it must cover only the directory page itself (list pages sit
 * in a `(list)` route group for this), never a detail or create page below it.
 */

const PROTECTED = path.join(__dirname, '..', '(protected)');

/** Loading views that draw one particular page (the page itself in skeleton
 *  mode, or a page's header), as opposed to a neutral fallback. */
function drawsDirectoryHeader(loadingFile: string): boolean {
  const raw = fs.readFileSync(loadingFile, 'utf8');
  if (raw.includes('<SkeletonMode>')) return true;
  const source = raw.replace(/directoryCrumb\(\s*PAGE_HEADERS\.\w+\s*\)/g, '');
  return /PAGE_HEADERS\.\w+/.test(source);
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

function loadingFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const child = path.join(dir, entry.name);
    if (entry.isDirectory()) found.push(...loadingFiles(child));
    else if (entry.name === 'loading.tsx') found.push(child);
  }
  return found;
}

describe('route loading boundaries', () => {
  it('never shows a directory header in place of a page below it', () => {
    const borrowed = loadingFiles(PROTECTED)
      .filter(drawsDirectoryHeader)
      .flatMap(loading =>
        pageDirs(path.dirname(loading)).map(
          dir =>
            `${path.relative(PROTECTED, dir)} <- ${path.relative(PROTECTED, loading)}`
        )
      );

    expect(borrowed).toEqual([]);
  });
});
