import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Knowledge',
};

export default function KnowledgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
