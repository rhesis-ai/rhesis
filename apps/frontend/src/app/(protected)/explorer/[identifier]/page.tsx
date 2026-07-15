import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import ExplorerDetail from './components/ExplorerDetail';

interface ExplorerDetailPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

export default async function ExplorerDetailPage({
  params,
}: ExplorerDetailPageProps) {
  const { identifier } = await params;
  const session = await auth();

  if (!session || session.error) {
    throw new Error('No session token available');
  }

  const clientFactory = await createServerApiFactory();
  const explorerClient = clientFactory.getExplorerClient();

  try {
    const [treeNodes, topics] = await Promise.all([
      explorerClient.getTree(identifier),
      explorerClient.getTopics(identifier),
    ]);

    const tests = treeNodes.filter(node => node.label !== 'topic_marker');

    let testSetName = identifier;
    try {
      const testSetsClient = clientFactory.getTestSetsClient();
      const testSet = await testSetsClient.getTestSet(identifier);
      testSetName = testSet.name || identifier;
    } catch (error) {
      notFoundIfEntityMissing(error);
    }

    return (
      <ExplorerDetail
        tests={tests}
        topics={topics}
        testSetName={testSetName}
        testSetId={identifier}
        sessionToken={session.session_token ?? ''}
      />
    );
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }
}
