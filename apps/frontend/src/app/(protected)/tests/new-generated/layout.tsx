import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Generate Tests | Rhesis AI',
};

export default function GenerateTestsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageContainer
      title="Generate Tests"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Generate Tests', path: '/tests/new-generated' },
      ]}
    >
      {children}
    </PageContainer>
  );
}
