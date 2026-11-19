import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Signing out' };

export default function SignOutLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
