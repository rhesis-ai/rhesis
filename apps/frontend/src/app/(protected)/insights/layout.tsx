import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Insights',
};

export default function InsightsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
