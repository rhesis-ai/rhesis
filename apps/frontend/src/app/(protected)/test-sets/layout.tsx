import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test Sets',
};

export default function TestSetsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
