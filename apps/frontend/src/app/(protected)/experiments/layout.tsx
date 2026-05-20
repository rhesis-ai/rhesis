import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Experiments',
};

export default function ExperimentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
