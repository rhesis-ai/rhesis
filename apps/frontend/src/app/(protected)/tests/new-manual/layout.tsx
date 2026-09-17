import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Manual Test Writer',
};

export default function NewTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
