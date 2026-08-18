import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Requirements',
};

export default function RequirementsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
