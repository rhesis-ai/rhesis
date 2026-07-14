import { getClientApiBaseUrl } from '@/utils/url-resolver';

export interface TermsStatus {
  terms_accepted: boolean;
  has_prior_acceptance: boolean;
}

export async function fetchTermsStatus(
  sessionToken: string
): Promise<TermsStatus> {
  const response = await fetch(`${getClientApiBaseUrl()}/auth/terms-status`, {
    headers: {
      Authorization: `Bearer ${sessionToken}`,
    },
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch terms status (${response.status})`);
  }
  const data = await response.json();
  return {
    terms_accepted: Boolean(data.terms_accepted),
    has_prior_acceptance: Boolean(data.has_prior_acceptance),
  };
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
