/**
 * @jest-environment node
 *
 * The module under test imports `next/server`, which needs the Web `Request`
 * global that the default jsdom environment does not provide.
 */
import { resolveTimeoutMs } from '../backend-proxy';

/**
 * The timeout budget the BFF proxy gives an upstream call.
 *
 * A path missing from the long-running lists gets the 10s CRUD budget, and any
 * call that waits on a model blows through it — the caller sees a 504 from the
 * proxy while the backend is still working, which reads as a broken feature
 * rather than a slow one.
 */
describe('resolveTimeoutMs', () => {
  const CRUD_MS = 10_000;
  const LONG_MS = 300_000;

  it('gives ordinary CRUD the short budget', () => {
    expect(resolveTimeoutMs('/metrics/abc/tuning/cases')).toBe(CRUD_MS);
    expect(resolveTimeoutMs('/metrics')).toBe(CRUD_MS);
  });

  it('gives a metric rewritten from its reviews the long budget', () => {
    // Synchronous and one generation call, so the response is held until the
    // model answers.
    expect(resolveTimeoutMs('/metrics/abc/tuning/improve')).toBe(LONG_MS);
  });

  it('gives a tuning run the short budget', () => {
    // Starting a run returns 202 straight away — the work is a background task.
    expect(resolveTimeoutMs('/metrics/abc/tuning/run')).toBe(CRUD_MS);
  });

  it('still recognises the paths that were already long-running', () => {
    expect(resolveTimeoutMs('/services/generate/tests')).toBe(LONG_MS);
    expect(resolveTimeoutMs('/test_sets/abc/generate_outputs')).toBe(LONG_MS);
  });
});
