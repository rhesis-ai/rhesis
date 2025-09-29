import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Endpoints',
};

export default function EndpointsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
