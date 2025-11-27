import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Create New Endpoint',
};

export default function NewEndpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
