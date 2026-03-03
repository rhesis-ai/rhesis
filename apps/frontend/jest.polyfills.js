/**
 * Pre-environment polyfills for Jest.
 *
 * This file runs via jest.config.js `setupFiles` before the test framework
 * and test environment are initialized.
 *
 * Currently a placeholder — add polyfills here if tests that use MSW node
 * server (msw/node) require fetch API globals not provided by the jsdom
 * environment. For example, install `whatwg-fetch` and add:
 *
 *   require('whatwg-fetch');
 */
