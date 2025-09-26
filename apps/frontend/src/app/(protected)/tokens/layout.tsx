import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'API Tokens',
};

export default function TokensLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
