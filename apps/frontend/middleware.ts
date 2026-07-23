// Next.js middleware entrypoint.
//
// The middleware logic itself lives in `./src/proxy.ts` (so it can be unit-tested
// in isolation), but Next.js only invokes middleware from a top-level
// `middleware.ts` file at the project root. Without this entrypoint the proxy
// is dead code.
//
// `export { proxy as middleware }` is the canonical Next.js pattern for
// re-exporting a middleware function from a non-default file. `config` is
// the matcher configuration consumed by Next.js.
export { proxy as middleware, config } from './src/proxy';
