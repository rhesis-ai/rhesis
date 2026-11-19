import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Sign in' };

export default function SignInLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
