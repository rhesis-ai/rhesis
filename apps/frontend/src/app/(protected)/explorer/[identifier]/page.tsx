import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import { entityErrorView } from '@/utils/entity-error-view';
import ExplorerDetail from './components/ExplorerDetail';
import { requireSession } from '@/utils/require-session';
import DocumentTitle from '@/components/common/DocumentTitle';
import { detailPageTitle } from '@/utils/document-title';

interface ExplorerDetailPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

export default async function ExplorerDetailPage({
  params,
}: ExplorerDetailPageProps) {
  const { identifier } = await params;
  await requireSession();

  const clientFactory = await createServerApiFactory();
  const explorerClient = clientFactory.getExplorerClient();

  // Only needs `identifier`; fails open to the identifier as a fallback name.
  const testSetsClient = clientFactory.getTestSetsClient();
  const testSetNamePromise = testSetsClient
    .getTestSet(identifier)
    .then(testSet => testSet.name || identifier)
    .catch(error => {
      notFoundIfEntityMissing(error);
      return identifier;
    });

  try {
    const [treeNodes, topics, testSetName] = await Promise.all([
      explorerClient.getTree(identifier),
      explorerClient.getTopics(identifier),
      testSetNamePromise,
    ]);

    const tests = treeNodes.filter(node => node.label !== 'topic_marker');

    return (
      <>
        <DocumentTitle
          title={detailPageTitle(
            testSetName === identifier ? null : testSetName,
            'Explorer'
          )}
        />
        <ExplorerDetail
          tests={tests}
          topics={topics}
          testSetName={testSetName}
          testSetId={identifier}
        />
      </>
    );
  } catch (error) {
    const errorView = entityErrorView(error);
    if (errorView) return errorView;
    throw error;
  }
}
