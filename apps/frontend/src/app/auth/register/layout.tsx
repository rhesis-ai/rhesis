import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Create account' };

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
