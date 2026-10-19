export async function register() {
  // The env check uses `process.exit`, which the Edge runtime does not have.
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { enforceEnv } = await import('@/config/enforce-env');
    enforceEnv();
  }
}
