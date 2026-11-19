import { Metadata } from 'next';

export const metadata: Metadata = { title: 'Magic link sign-in' };

export default function MagicLinkLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
