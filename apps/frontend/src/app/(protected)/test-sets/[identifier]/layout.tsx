import { Metadata } from 'next';

// This will be overridden by the dynamic generation in page.tsx
export const metadata: Metadata = {
  title: 'Test Set Details',
};

interface TestSetDetailLayoutProps {
  children: React.ReactNode;
}

export default function TestSetDetailLayout({
  children,
}: TestSetDetailLayoutProps) {
  return children;
}
