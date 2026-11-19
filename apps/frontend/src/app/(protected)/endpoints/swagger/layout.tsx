import { Metadata } from 'next';
import DocumentTitle from '@/components/common/DocumentTitle';

export const metadata: Metadata = {
  title: 'Import Swagger Endpoint',
};

export default function SwaggerEndpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <DocumentTitle title="Import Swagger Endpoint" />
      {children}
    </>
  );
}
