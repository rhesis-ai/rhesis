import { Metadata } from 'next';
import DocumentTitle from '@/components/common/DocumentTitle';

export const metadata: Metadata = {
  title: 'Manual Test Writer',
};

export default function NewTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <DocumentTitle title="Manual Test Writer" />
      {children}
    </>
  );
}
