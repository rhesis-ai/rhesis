'use client';

import React from 'react';
import EndpointForm from '../components/EndpointForm';
import { PageContainer } from '@toolpad/core';

export default function NewEndpointPage() {
  const breadcrumbs = [
    { title: 'Endpoints', path: '/endpoints' },
    { title: 'Create New Endpoint' },
  ];

  return (
    <PageContainer title="Create New Endpoint" breadcrumbs={breadcrumbs}>
      <EndpointForm />
    </PageContainer>
  );
}
