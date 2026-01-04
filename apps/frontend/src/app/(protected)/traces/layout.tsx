import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Traces',
};

export default function TracesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
