import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test explorer',
};

export default function AdaptiveTestingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
