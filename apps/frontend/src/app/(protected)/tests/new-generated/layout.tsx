import { Metadata } from 'next';
import { PageLayout } from '@/components/layout/PageLayout';

export const metadata: Metadata = {
  title: 'Generate Tests | Rhesis AI',
};

export default function GenerateTestsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageLayout
      title="Generate Tests"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Generate Tests', path: '/tests/new-generated' },
      ]}
    >
      {children}
    </PageLayout>
  );
}
