export const dynamic = 'force-dynamic';

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { entityErrorView } from '@/utils/entity-error-view';
import SourcePreviewClientWrapper from './components/SourcePreviewClientWrapper';
import { requireSession } from '@/utils/require-session';

interface SourcePreviewPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

/**
 * Server component for the Source Preview page
 * Fetches source data and renders the client wrapper component
 */
export default async function SourcePreviewPage({
  params,
}: SourcePreviewPageProps) {
  const session = await requireSession();

  const apiFactory = await createServerApiFactory();
  const sourcesClient = apiFactory.getSourcesClient();

  // Await params before using its properties (Next.js 15 requirement)
  const resolvedParams = await params;

  let source;
  try {
    source = await sourcesClient.getSourceWithContent(
      resolvedParams.identifier as `${string}-${string}-${string}-${string}-${string}`
    );
  } catch (error) {
    const errorView = entityErrorView(error);
    if (errorView) return errorView;
    throw error;
  }

  return (
    <SourcePreviewClientWrapper
      source={source}
      currentUserId={session.user?.id || ''}
      currentUserName={session.user?.name || ''}
      currentUserPicture={session.user?.picture || undefined}
    />
  );
}
