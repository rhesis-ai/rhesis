import { Metadata } from 'next';

export const metadata: Metadata = { title: 'SSO sign-in failed' };

export default function SSOErrorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
