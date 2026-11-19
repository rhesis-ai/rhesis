import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Organization',
};

export default function OrganizationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
