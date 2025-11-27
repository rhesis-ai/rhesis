'use client';

import React from 'react';
import SwaggerEndpointForm from '../components/SwaggerEndpointForm';
import { PageContainer } from '@toolpad/core/PageContainer';

export default function SwaggerEndpointPage() {
  const breadcrumbs = [
    { title: 'Endpoints', path: '/endpoints' },
    { title: 'Import Swagger Endpoint' },
  ];

  return (
    <PageContainer title="Import Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageContainer>
  );
}
