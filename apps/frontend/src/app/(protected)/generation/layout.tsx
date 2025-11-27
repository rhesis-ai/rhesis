import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Generation',
};

export default function GenerationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
