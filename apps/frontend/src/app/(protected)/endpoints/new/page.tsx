'use client';

import React from 'react';
import EndpointForm from '../components/EndpointForm';
import { PageLayout } from '@/components/layout/PageLayout';

export default function NewEndpointPage() {
  const breadcrumbs = [
    { title: 'Endpoints', path: '/endpoints' },
    { title: 'Create New Endpoint' },
  ];

  return (
    <PageLayout title="Create New Endpoint" breadcrumbs={breadcrumbs}>
      <EndpointForm />
    </PageLayout>
  );
}
