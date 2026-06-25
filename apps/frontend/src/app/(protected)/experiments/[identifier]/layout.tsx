import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Experiment',
};

export default function ExperimentDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
