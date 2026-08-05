/**
 * Pre-environment polyfills for Jest.
 *
 * This file runs via jest.config.js `setupFiles` before the test framework
 * and test environment are initialized.
 *
 * Add polyfills here if tests that use MSW node server (msw/node) require
 * fetch API globals not provided by the jsdom environment. For example,
 * install `whatwg-fetch` and add:
 *
 *   require('whatwg-fetch');
 */

// jsdom does not expose structuredClone, which Node has had since 17.
// @mui/x-internal-gestures calls it while constructing its gesture manager,
// so every test that renders an @mui/x-charts chart throws without this.
// v8's serialize/deserialize gives the same structured-clone semantics for
// the plain config objects involved here.
if (typeof globalThis.structuredClone !== 'function') {
  // eslint-disable-next-line @typescript-eslint/no-require-imports -- setupFiles runs as CJS before the module system is set up, so import is unavailable here
  const { deserialize, serialize } = require('node:v8');
  globalThis.structuredClone = value => deserialize(serialize(value));
}
