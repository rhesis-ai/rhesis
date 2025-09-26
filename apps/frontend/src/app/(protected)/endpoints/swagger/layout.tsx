import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Swagger Endpoint | Rhesis AI',
  description: 'Add a new API endpoint using Swagger/OpenAPI specification',
};

export default function SwaggerEndpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
