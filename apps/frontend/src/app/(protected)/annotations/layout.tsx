import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Annotations',
};

export default function AnnotationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
