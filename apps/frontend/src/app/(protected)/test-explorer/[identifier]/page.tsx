import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageContainer } from '@toolpad/core/PageContainer';
import AdaptiveTestsExplorer from './components/AdaptiveTestsExplorer';

interface TestExplorerDetailPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

export default async function TestExplorerDetailPage({
  params,
}: TestExplorerDetailPageProps) {
  try {
    const { identifier } = await params;
    const session = await auth();

    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const testSetsClient = clientFactory.getTestSetsClient();

    // Fetch the test set
    const testSet = await testSetsClient.getTestSet(identifier);

    // Fetch tests for this test set
    const testsResponse = await testSetsClient.getTestSetTests(identifier, {
      skip: 0,
      limit: 100,
    });

    // Extract unique topics from tests in this test set
    const topicSet = new Set<string>();
    testsResponse.data.forEach(test => {
      const topicName = typeof test.topic === 'string' ? test.topic : test.topic?.name;
      if (topicName) {
        topicSet.add(topicName);
      }
    });
    const topics = Array.from(topicSet).map((name, index) => ({
      id: `derived-${index}` as `${string}-${string}-${string}-${string}-${string}`,
      name,
    }));

    // Transform tests to display format with input, output, score
    // Metadata is stored in test_metadata field
    // Filter out topic_marker entries (internal tree structure markers)
    const adaptiveTests = testsResponse.data
      .filter(test => {
        const metadata = test.test_metadata || {};
        return metadata.label !== 'topic_marker';
      })
      .map(test => {
        const metadata = test.test_metadata || {};
        return {
          id: test.id,
          input: test.prompt?.content || '',
          output: metadata.output || '[no output]',
          score: metadata.model_score ?? null,
          topic: typeof test.topic === 'string' ? test.topic : test.topic?.name || '',
          label: metadata.label || '',
        };
      });

    return (
      <PageContainer
        title={testSet.name || 'Test Explorer'}
        breadcrumbs={[
          { title: 'Test Explorer', path: '/test-explorer' },
          { title: testSet.name || 'Details', path: '' },
        ]}
      >
        <Box sx={{ mb: 2 }}>
          <Typography variant="body1" color="text.secondary">
            Adaptive testing results for this test set
          </Typography>
        </Box>

        {/* Tests Explorer with Topic Tree */}
        <AdaptiveTestsExplorer
          tests={adaptiveTests}
          topics={topics.map(t => ({ id: t.id, name: t.name }))}
          loading={false}
          sessionToken={session.session_token}
          testSetId={identifier}
        />
      </PageContainer>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Error loading test explorer details: {errorMessage}
        </Typography>
      </Box>
    );
  }
}
