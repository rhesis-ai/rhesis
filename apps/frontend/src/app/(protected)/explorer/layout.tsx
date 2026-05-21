import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Explorer',
};

export default function ExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
