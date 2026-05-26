'use client';

import React from 'react';
import SwaggerEndpointForm from '../components/SwaggerEndpointForm';
import { PageLayout } from '@/components/layout/PageLayout';

export default function SwaggerEndpointPage() {
  const breadcrumbs = [
    { label: 'Endpoints', href: '/endpoints' },
    { label: 'Import Swagger Endpoint' },
  ];

  return (
    <PageLayout title="Import Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageLayout>
  );
}
