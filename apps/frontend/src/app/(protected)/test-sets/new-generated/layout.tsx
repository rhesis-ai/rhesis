import { Metadata } from 'next';
import { PageLayout } from '@/components/layout/PageLayout';

export const metadata: Metadata = {
  title: 'Generate Test Set | Rhesis AI',
};

export default function GenerateTestSetLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageLayout
      title="Generate Test Set"
      description="Describe what you want to test and let AI generate a curated set of test cases for your application."
      breadcrumbs={[
        { label: 'Test Sets', href: '/test-sets' },
        { label: 'Generate Test Set', href: '/test-sets/new-generated' },
      ]}
    >
      {children}
    </PageLayout>
  );
}
