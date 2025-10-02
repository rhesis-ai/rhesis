import { Metadata } from 'next';
import { PageContainer } from '@toolpad/core/PageContainer';

export const metadata: Metadata = {
  title: 'Configure Test Generation | Rhesis AI',
};

export default function TestConfigurationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PageContainer
      title="Configure Test Generation"
      breadcrumbs={[
        { title: 'Tests', path: '/tests' },
        { title: 'Test Generation', path: '/tests/generate' },
        { title: 'Configure', path: '/tests/generate/configure' },
      ]}
    >
      {children}
    </PageContainer>
  );
}
