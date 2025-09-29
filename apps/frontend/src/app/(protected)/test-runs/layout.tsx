import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test Runs',
};

export default function TestRunsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
