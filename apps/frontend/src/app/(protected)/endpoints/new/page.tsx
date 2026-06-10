'use client';

import { PageLayout } from '@/components/layout/PageLayout';
import EndpointForm from '../components/EndpointForm';

export default function NewEndpointPage() {
  const breadcrumbs = [
    { label: 'Endpoints', href: '/endpoints' },
    { label: 'Create New Endpoint' },
  ];

  return (
    <PageLayout title="Create New Endpoint" breadcrumbs={breadcrumbs}>
      <EndpointForm />
    </PageLayout>
  );
}
