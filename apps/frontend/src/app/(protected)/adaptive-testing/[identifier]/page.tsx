import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import AdaptiveTestingDetail from './components/AdaptiveTestingDetail';

interface AdaptiveTestingDetailPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

export default async function AdaptiveTestingDetailPage({
  params,
}: AdaptiveTestingDetailPageProps) {
  try {
    const { identifier } = await params;
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(
      session.session_token
    );
    const adaptiveTestingClient =
      clientFactory.getAdaptiveTestingClient();

    // Fetch tree data (all nodes) and topics in parallel
    const [treeNodes, topics] = await Promise.all([
      adaptiveTestingClient.getTree(identifier),
      adaptiveTestingClient.getTopics(identifier),
    ]);

    // Separate tests from topic markers
    const tests = treeNodes.filter(
      node => node.label !== 'topic_marker'
    );

    // Try to get the test set name for the breadcrumb
    let testSetName = identifier;
    try {
      const testSetsClient =
        clientFactory.getTestSetsClient();
      const testSet =
        await testSetsClient.getTestSet(identifier);
      testSetName = testSet.name || identifier;
    } catch {
      // Fall back to identifier if test set fetch fails
    }

    return (
      <PageContainer
        title={testSetName}
        breadcrumbs={[
          {
            title: 'Adaptive Testing',
            path: '/adaptive-testing',
          },
          { title: testSetName, path: '' },
        ]}
      >
        <AdaptiveTestingDetail
          tests={tests}
          topics={topics}
          testSetName={testSetName}
          testSetId={identifier}
          sessionToken={session.session_token}
        />
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Error loading adaptive testing details:{' '}
          {errorMessage}
        </Typography>
      </Box>
    );
  }
}
