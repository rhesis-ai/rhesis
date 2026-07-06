'use client';

import React from 'react';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import ApiIcon from '@mui/icons-material/Api';

export default function ApiClientsEmptyState() {
  return (
    <EntityEmptyState
      icon={ApiIcon}
      title="API Clients are an Enterprise feature"
      description="Issue scoped OAuth client credentials for machine-to-machine access to your organization's data."
      actionLabel="Learn about Enterprise"
      onAction={() =>
        window.open('https://rhesis.ai/pricing', '_blank', 'noopener,noreferrer')
      }
    />
  );
}
