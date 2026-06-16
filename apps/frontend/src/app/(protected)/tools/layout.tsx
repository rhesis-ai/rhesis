import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Tools',
};

export default function ToolLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
