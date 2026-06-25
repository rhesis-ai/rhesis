import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Manual Test Writer | Rhesis AI',
};

export default function NewTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
