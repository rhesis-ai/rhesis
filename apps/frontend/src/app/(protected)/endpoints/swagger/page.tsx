import SwaggerEndpointForm from '../components/SwaggerEndpointForm';
import { PageLayout } from '@/components/layout/PageLayout';
import { PAGE_HEADERS, directoryCrumb } from '@/constants/page-headers';

export default function SwaggerEndpointPage() {
  const breadcrumbs = [
    directoryCrumb(PAGE_HEADERS.endpoints),
    { label: 'Import Swagger Endpoint' },
  ];

  return (
    <PageLayout title="Import Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageLayout>
  );
}
