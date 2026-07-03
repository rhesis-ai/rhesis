// ee/frontend has no node_modules of its own (@rhesis/ee-frontend is a
// `file:` dependency, symlinked into apps/frontend/node_modules) — so this
// re-exports apps/frontend's config by relative import rather than
// re-declaring the plugin list. Plugin bare-specifier imports inside that
// file resolve relative to *its own* path (apps/frontend/node_modules),
// which works regardless of where eslint is invoked from.
//
// Run from this directory (`ee/frontend`) so ESLint's flat-config base path
// includes `src/` — see the `lint`/`format` scripts in package.json.
import baseConfig from '../../apps/frontend/eslint.config.mjs';

export default [...baseConfig];
