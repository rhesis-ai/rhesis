import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Import Swagger Endpoint',
};

export default function SwaggerEndpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
