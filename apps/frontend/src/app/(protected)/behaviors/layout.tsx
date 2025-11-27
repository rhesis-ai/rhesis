import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Behaviors',
};

export default function BehaviorsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
