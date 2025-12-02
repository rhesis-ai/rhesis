import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Tasks',
};

export default function TasksLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
