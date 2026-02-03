import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test Explorer',
};

export default function TestExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
