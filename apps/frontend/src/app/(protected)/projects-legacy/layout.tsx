import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Projects Legacy',
};

export default function ProjectsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
} 