import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Test Generation | Rhesis AI',
};

export default function TestGenerationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageContainer
      title="Test Generation"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Test Generation', path: '/tests/generate' },
      ]}
    >
      {children}
    </PageContainer>
  );
}
