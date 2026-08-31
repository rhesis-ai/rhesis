import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import ExplorerDetail from './components/ExplorerDetail';
import { requireSession } from '@/utils/require-session';

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
      <ExplorerDetail
        tests={tests}
        topics={topics}
        testSetName={testSetName}
        testSetId={identifier}
      />
    );
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }
}
