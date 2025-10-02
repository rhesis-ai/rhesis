'use client';

import React from 'react';
import SwaggerEndpointForm from '../components/SwaggerEndpointForm';
import { PageContainer } from '@toolpad/core/PageContainer';

export default function SwaggerEndpointPage() {
  return (
    <PageContainer
      title="New Swagger Endpoint"
      breadcrumbs={[
        { title: 'Endpoints', path: '/endpoints' },
        { title: 'Add Swagger Endpoint' },
      ]}
    >
      <SwaggerEndpointForm />
    </PageContainer>
  );
}
