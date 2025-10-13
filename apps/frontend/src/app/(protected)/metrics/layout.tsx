import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Metrics',
};

export default function MetricsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
