import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Playground',
};

export default function PlaygroundLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
