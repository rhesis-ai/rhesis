import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Verify email' };

export default function VerifyEmailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
