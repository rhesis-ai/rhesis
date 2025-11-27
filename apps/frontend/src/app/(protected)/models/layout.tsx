import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Models',
};

export default function ModelsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
