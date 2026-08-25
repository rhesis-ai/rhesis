import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Jobs',
};

export default function JobsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
