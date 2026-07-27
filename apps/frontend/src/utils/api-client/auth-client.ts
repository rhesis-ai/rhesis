export interface TermsStatus {
  terms_accepted: boolean;
  has_prior_acceptance: boolean;
}

export async function fetchTermsStatus(): Promise<TermsStatus> {
  const response = await fetch('/api/backend/auth/terms-status', {
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

export async function acceptTerms(): Promise<void> {
  const response = await fetch('/api/backend/auth/accept-terms', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to record terms acceptance');
  }
}
