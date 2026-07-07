'use client';

import React from 'react';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';

export default function SSOEmptyState() {
  return (
    <EntityEmptyState
      icon={VerifiedUserIcon}
      title="Single Sign-On is an Enterprise feature"
      description="Let your team sign in with your identity provider (SAML, OIDC) instead of managing separate passwords."
      actionLabel="Learn about Enterprise"
      onAction={() =>
        window.open(
          'https://rhesis.ai/pricing',
          '_blank',
          'noopener,noreferrer'
        )
      }
    />
  );
}
