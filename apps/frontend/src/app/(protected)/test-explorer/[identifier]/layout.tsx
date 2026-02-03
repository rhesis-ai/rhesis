import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Test Explorer - Details',
};

export default function TestExplorerDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
