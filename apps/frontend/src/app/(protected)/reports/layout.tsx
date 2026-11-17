import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Reports',
};

export default function ReportsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
