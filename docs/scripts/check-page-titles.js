#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Stops page titles from repeating the site name.
 *
 * `src/app/layout.jsx` sets a title template of "%s – Rhesis", so Next appends
 * the brand to every page title itself. A frontmatter `title: Endpoints – Rhesis`
 * therefore renders as "Endpoints – Rhesis – Rhesis" in the browser tab and in
 * search results. The suffix is easy to copy from a neighbouring page, which is
 * how nine of them got it.
 *
 * The brand may still appear inside a title where it reads as prose
 * ("Getting Started with Rhesis") or as part of a name ("RhesisClient") — only a
 * trailing separator + brand is a violation.
 */

const CONTENT_DIR = path.resolve(__dirname, '..', 'content');

// Matches " – Rhesis", " | Rhesis AI", " - Rhesis Python SDK" at the very end.
const BRAND_SUFFIX = /\s*[–—|-]\s*Rhesis(\s+[\w.&]+){0,2}\s*$/i;

function mdxFiles(dir) {
  const found = [];
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, item.name);
    if (item.isDirectory()) {
      if (!item.name.startsWith('.') && item.name !== 'node_modules') found.push(...mdxFiles(full));
    } else if (item.isFile() && item.name.endsWith('.mdx') && !item.name.startsWith('_')) {
      found.push(full);
    }
  }
  return found;
}

function frontmatterTitle(source) {
  const block = source.match(/^---\n([\s\S]*?)\n---/);
  if (!block) return null;
  const line = block[1].match(/^title:\s*(.+)$/m);
  return line ? line[1].trim().replace(/^['"]|['"]$/g, '') : null;
}

function main() {
  const files = mdxFiles(CONTENT_DIR);
  const violations = [];

  for (const file of files) {
    const title = frontmatterTitle(fs.readFileSync(file, 'utf8'));
    if (!title) continue;

    if (BRAND_SUFFIX.test(title)) {
      violations.push({
        rel: path.relative(path.dirname(CONTENT_DIR), file),
        title,
        fix: title.replace(BRAND_SUFFIX, '').trim(),
      });
    }
  }

  if (violations.length === 0) {
    console.log(`✅ Page title checks passed (${files.length} pages).`);
    return;
  }

  const plural = violations.length === 1 ? 'title repeats' : 'titles repeat';
  console.error(`❌ ${violations.length} page ${plural} the site name:\n`);
  for (const v of violations) {
    console.error(`  ${v.rel}`);
    console.error(`    title: ${v.title}   → renders as "${v.title} – Rhesis"`);
    console.error(`    Fix: title: ${v.fix}\n`);
  }
  console.error('The layout appends " – Rhesis" to every title; the page must not add it too.\n');

  process.exit(1);
}

if (require.main === module) {
  main();
}
