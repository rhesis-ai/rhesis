#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Keeps docs image weight out of git history.
 *
 * Screenshots are re-shot in batches every few months, so each PNG batch lands
 * permanently in history at ~3.35x the WebP cost. Two rules:
 *
 *   A. Screenshots must be WebP.
 *   B. No raster asset over MAX_KB, whatever its format.
 *
 * BASELINE lists the assets that predate these rules. It may only shrink — a
 * stale entry is an error, so converting a file forces its removal here.
 */

const PUBLIC_DIR = path.resolve(__dirname, '..', 'src', 'public');
const SCREENSHOT_PREFIX = 'screenshots/';
const MAX_KB = 400;

// Raster formats subject to the size budget. SVG and .ico are exempt: SVG is
// text and compresses, .ico is required by browsers at a fixed path.
const RASTER = /\.(png|jpe?g|gif|webp|avif)$/i;

// Known debt, recorded 2026-08-10. Delete each line as the file is converted.
const BASELINE = new Set([
  'changelog/v0.4.1/Release 0.4.1.gif', // animated; needs animated-WebP conversion
  'screenshots/rhesis-ai-auto-login-page.png',
  'screenshots/rhesis-ai-create-metrics.png',
  'screenshots/rhesis-ai-dashboard-dark.png',
  'screenshots/rhesis-ai-dashboard-docker-spinup.png',
  'screenshots/rhesis-ai-dashboard.png',
  'screenshots/rhesis-ai-endpoint-request-settings.png',
  'screenshots/rhesis-ai-endpoint-test-connection.png',
  'screenshots/rhesis-ai-endpoints-auto-configure.png',
  'screenshots/rhesis-ai-generation-select-test-type.png',
  'screenshots/rhesis-ai-generation-test-configuration.png',
  'screenshots/rhesis-ai-generation-test-samples.png',
  'screenshots/rhesis-ai-metrics-assign.png',
  'screenshots/rhesis-ai-multimodal-playground.png',
  'screenshots/rhesis-ai-multimodal-test-attach.png',
  'screenshots/rhesis-ai-multimodal-trace.png',
  'screenshots/rhesis-ai-polyphemus-access.png',
  'screenshots/rhesis-ai-project-parameters.png',
  'screenshots/rhesis-ai-projects-detail-view.png',
  'screenshots/rhesis-ai-projects-overview.png',
  'screenshots/rhesis-ai-team.png',
  'screenshots/rhesis-ai-test-generation.png',
  'screenshots/rhesis-ai-test-set-execution.png',
  'screenshots/rhesis-ai-testsets-import-file.png',
  'screenshots/rhesis-ai-testsets-import-garak.png',
  'screenshots/rhesis-ai-testsets-inspect-data.png',
  'screenshots/rhesis-test-explorer.png',
]);

function walk(dir, rootDir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, rootDir, out);
    } else if (entry.isFile()) {
      out.push(path.relative(rootDir, full).split(path.sep).join('/'));
    }
  }
  return out;
}

function main() {
  if (!fs.existsSync(PUBLIC_DIR)) {
    console.error(`Public directory not found: ${PUBLIC_DIR}`);
    process.exit(1);
  }

  const files = walk(PUBLIC_DIR, PUBLIC_DIR).filter((f) => RASTER.test(f));
  const violations = [];
  const seen = new Set();

  for (const rel of files) {
    const kb = Math.round(fs.statSync(path.join(PUBLIC_DIR, rel)).size / 1024);

    if (BASELINE.has(rel)) {
      seen.add(rel);
      continue;
    }

    if (rel.startsWith(SCREENSHOT_PREFIX) && !rel.endsWith('.webp')) {
      violations.push({
        rel,
        rule: 'format',
        detail: `${path.extname(rel)} in screenshots/ (${kb} KB)`,
        fix: `cwebp -lossless "public/${rel}" -o "public/${rel.replace(/\.[^.]+$/, '.webp')}"`,
      });
      continue;
    }

    if (kb > MAX_KB) {
      violations.push({
        rel,
        rule: 'size',
        detail: `${kb} KB exceeds the ${MAX_KB} KB budget`,
        fix: 'Re-encode smaller, or crop/resize before committing.',
      });
    }
  }

  // A baseline entry whose file is gone means the debt was paid — the line must go too.
  const stale = [...BASELINE].filter((rel) => !seen.has(rel));

  if (violations.length === 0 && stale.length === 0) {
    const debt = BASELINE.size;
    console.log(`✅ Image checks passed (${files.length} raster assets).`);
    if (debt > 0) {
      console.log(`   ${debt} baseline exemption${debt === 1 ? '' : 's'} remaining — see BASELINE in docs/scripts/check-image-formats.js`);
    }
    return;
  }

  if (violations.length > 0) {
    console.error(`❌ ${violations.length} image violation${violations.length === 1 ? '' : 's'}:\n`);
    for (const v of violations) {
      console.error(`  public/${v.rel}`);
      console.error(`    ${v.rule === 'format' ? 'Screenshots must be WebP' : 'Over size budget'}: ${v.detail}`);
      console.error(`    Fix: ${v.fix}\n`);
    }
    console.error('WebP costs ~3.35x less per screenshot and every version committed stays');
    console.error('in git history permanently.\n');
  }

  if (stale.length > 0) {
    console.error(`❌ ${stale.length} stale baseline entr${stale.length === 1 ? 'y' : 'ies'} — file gone, so remove the line from BASELINE in docs/scripts/check-image-formats.js:\n`);
    for (const rel of stale) {
      console.error(`  ${rel}`);
    }
    console.error('');
  }

  process.exit(1);
}

if (require.main === module) {
  main();
}
