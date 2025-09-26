import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Create New Test',
};

export default function NewTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
