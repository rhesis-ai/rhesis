export function isNotFoundApiError(error: unknown): boolean {
  if (!(error instanceof Error) || !('status' in error)) {
    return false;
  }

  const status = (error as Error & { status?: number }).status;
  return status === 404 || status === 410;
}
