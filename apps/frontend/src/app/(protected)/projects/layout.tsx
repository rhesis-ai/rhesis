import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Projects',
};

export default function ProjectsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
