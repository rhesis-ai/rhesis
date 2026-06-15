interface AuthConfigResponse {
  quick_start?: boolean;
}

export async function fetchQuickStartEnabled(): Promise<boolean> {
  try {
    const response = await fetch('/api/auth-config');
    if (!response.ok) {
      return false;
    }

    const data = (await response.json()) as AuthConfigResponse;
    return data.quick_start === true;
  } catch (_error) {
    return false;
  }
}
