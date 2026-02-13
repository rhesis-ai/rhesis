import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Adaptive Testing',
};

export default function AdaptiveTestingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
