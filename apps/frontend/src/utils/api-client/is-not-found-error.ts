export function getApiErrorStatus(error: unknown): number | undefined {
  if (!(error instanceof Error) || !('status' in error)) {
    return undefined;
  }

  return (error as Error & { status?: number }).status;
}

export function is404ApiError(error: unknown): boolean {
  return getApiErrorStatus(error) === 404;
}

export function isNotFoundApiError(error: unknown): boolean {
  const status = getApiErrorStatus(error);
  return status === 404 || status === 410;
}
