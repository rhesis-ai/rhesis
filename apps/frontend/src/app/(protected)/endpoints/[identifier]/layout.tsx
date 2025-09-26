import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Endpoint Details',
};

export default function EndpointDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
