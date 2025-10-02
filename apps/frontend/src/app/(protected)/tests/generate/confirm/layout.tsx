import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Confirm Test Generation | Rhesis AI',
};

export default function ConfirmTestGenerationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageContainer
      title="Confirm Test Generation"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Test Generation', path: '/tests/generate' },
        { title: 'Confirm', path: '/tests/generate/confirm' },
      ]}
    >
      {children}
    </PageContainer>
  );
}
