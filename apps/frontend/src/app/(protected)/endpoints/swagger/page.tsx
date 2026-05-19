'use client';

import React from 'react';
import SwaggerEndpointForm from '../components/SwaggerEndpointForm';
import { PageLayout } from '@/components/layout/PageLayout';

export default function SwaggerEndpointPage() {
  const breadcrumbs = [
    { title: 'Endpoints', path: '/endpoints' },
    { title: 'Import Swagger Endpoint' },
  ];

  return (
    <PageLayout title="Import Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageLayout>
  );
}
