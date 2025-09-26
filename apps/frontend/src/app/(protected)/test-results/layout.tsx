import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test Results',
};

export default function TestResultsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
