#!/usr/bin/env node
/**
 * Frontend EE boundary guard.
 *
 * Asserts that no source file under `apps/frontend/src/` (the MIT
 * core) statically imports from `@rhesis/ee-frontend`. The only
 * permitted reference is in `apps/frontend/src/ee_bootstrap.ts` --
 * the sanctioned bridge to the optional EE package.
 *
 * Mirror of `tests/backend/test_ee_boundary.py` for the frontend.
 * Pure Node + standard library, no npm install required, so it runs
 * in seconds in a clean CI sandbox without the full frontend build
 * environment. The same check is also enforced at lint time by the
 * `no-restricted-imports` rule in `eslint.config.mjs`; this script is
 * the CI-side belt to that suspenders.
 *
 * Usage:
 *   node apps/frontend/scripts/check-ee-boundary.mjs
 *
 * Exits 0 if the boundary holds, 1 if any violation is found.
 *
 * Why a regex and not a real parser?
 * ----------------------------------
 * The `@rhesis/ee-frontend` package name is unique enough that string
 * matching against `from '@rhesis/ee-frontend...'` and side-effect
 * `import '@rhesis/ee-frontend...'` is reliable in practice. Real
 * parsing would require pulling in the TypeScript compiler API (or
 * @babel/parser), which would mean an `npm install` and a much larger
 * CI job. The trade-off mirrors the backend's lightweight AST check
 * vs. a full pytest run.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..', 'src');
const ALLOWED = resolve(ROOT, 'ee_bootstrap.ts');
const REPO_ROOT = resolve(__dirname, '..', '..', '..');

// Match every realistic shape of a @rhesis/ee-frontend reference:
//   - `import ... from '@rhesis/ee-frontend'` (named, default, namespace)
//   - `import ... from '@rhesis/ee-frontend/...'` (subpath)
//   - `import '@rhesis/ee-frontend'` (side-effect)
//   - `require('@rhesis/ee-frontend')` (CommonJS)
//   - `import('@rhesis/ee-frontend')` (dynamic import expression)
// The `[\s\S]*?` between `import` and the quoted path covers multi-
// line and named imports where the `from` clause isn't on the same
// line as `import`.
const PATTERNS = [
  /import\s+[\s\S]*?from\s+['"](@rhesis\/ee-frontend(?:\/[^'"]*)?)['"]/g,
  /import\s+['"](@rhesis\/ee-frontend(?:\/[^'"]*)?)['"]/g,
  /require\s*\(\s*['"](@rhesis\/ee-frontend(?:\/[^'"]*)?)['"]\s*\)/g,
  /\bimport\s*\(\s*['"](@rhesis\/ee-frontend(?:\/[^'"]*)?)['"]\s*\)/g,
];

const FILE_EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']);
const SKIP_DIRS = new Set(['node_modules', '.next', 'dist', 'build', 'coverage', 'out']);

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (SKIP_DIRS.has(entry)) continue;
      yield* walk(full);
    } else if (st.isFile()) {
      const dotIdx = entry.lastIndexOf('.');
      if (dotIdx === -1) continue;
      if (!FILE_EXTS.has(entry.slice(dotIdx))) continue;
      yield full;
    }
  }
}

function findViolations() {
  const violations = [];
  for (const file of walk(ROOT)) {
    if (resolve(file) === ALLOWED) continue;

    const src = readFileSync(file, 'utf8');
    for (const re of PATTERNS) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(src)) !== null) {
        const lineno = src.slice(0, m.index).split('\n').length;
        const rel = relative(REPO_ROOT, file);
        violations.push(`${rel}:${lineno}: imports '${m[1]}'`);
      }
    }
  }
  return violations;
}

const violations = findViolations();
if (violations.length > 0) {
  console.error('EE boundary violation: core may not import from @rhesis/ee-frontend.\n');
  console.error('Move the EE-specific code into ee/frontend/, or plug into');
  console.error('a registry in apps/frontend/src/lib/extension-registries/');
  console.error('and register it from ee/frontend/src/bootstrap.ts.\n');
  console.error('The only file allowed to import from @rhesis/ee-frontend is');
  console.error('apps/frontend/src/ee_bootstrap.ts.\n');
  console.error('Violations:');
  for (const v of violations) console.error(`  ${v}`);
  process.exit(1);
}

console.log('OK: no @rhesis/ee-frontend imports found in core (apps/frontend/src/).');
