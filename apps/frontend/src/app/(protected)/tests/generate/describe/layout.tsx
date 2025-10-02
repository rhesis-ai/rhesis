import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Describe Test Requirements | Rhesis AI',
};

export default function DescribeTestLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageContainer
      title="Describe what you want to test"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Test Generation', path: '/tests/generate' },
        { title: 'Describe Requirements', path: '/tests/generate/describe' },
      ]}
    >
      {children}
    </PageContainer>
  );
}
