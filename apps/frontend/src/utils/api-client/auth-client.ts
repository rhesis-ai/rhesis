import { getClientApiBaseUrl } from '@/utils/url-resolver';

export async function fetchTermsStatus(sessionToken: string): Promise<boolean> {
  const response = await fetch(`${getClientApiBaseUrl()}/auth/terms-status`, {
    headers: {
      Authorization: `Bearer ${sessionToken}`,
    },
    credentials: 'include',
  });
  if (!response.ok) {
    return false;
  }
  const data = await response.json();
  return Boolean(data.terms_accepted);
}

export async function acceptTerms(sessionToken: string): Promise<void> {
  const response = await fetch(`${getClientApiBaseUrl()}/auth/accept-terms`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${sessionToken}`,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to record terms acceptance');
  }
}
