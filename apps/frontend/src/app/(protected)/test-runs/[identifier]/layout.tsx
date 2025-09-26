import { Metadata } from 'next';

// This will be overridden by the dynamic generation in page.tsx
export const metadata: Metadata = {
  title: 'Test Run Details',
};

interface TestRunDetailLayoutProps {
  children: React.ReactNode;
}

export default function TestRunDetailLayout({
  children,
}: TestRunDetailLayoutProps) {
  return children;
}
