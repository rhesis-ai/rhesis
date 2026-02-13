import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Adaptive Testing - Details',
};

export default function AdaptiveTestingDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
