import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test explorer - Details',
};

export default function AdaptiveTestingDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
