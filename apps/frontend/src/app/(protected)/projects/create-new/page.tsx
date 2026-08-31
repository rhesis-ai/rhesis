import { Box } from '@mui/material';
import CreateProjectClient from './components/CreateProjectClient';
import { UUID } from 'crypto';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';

export default async function CreateProjectPage() {
  const session = await requireSession();

  if (!session?.user?.id) {
    throw new Error('No user ID available in session');
  }

  // Get organization ID from session or fetch it from API
  let organizationId: UUID | undefined;
  if (session.user && 'organization_id' in session.user) {
    organizationId = session.user.organization_id as UUID;
  } else {
    try {
      // Fetch user data to get organization ID
      const apiFactory = await createServerApiFactory();
      const usersClient = apiFactory.getUsersClient();
      const userData = await usersClient.getUser(session.user.id);
      organizationId = userData.organization_id;
    } catch (error) {
      console.error(
        'Failed to fetch organization ID for project creation:',
        error
      );
    }
  }

  return (
    <Box sx={{ p: 0 }}>
      <CreateProjectClient
        userId={session.user.id as UUID}
        organizationId={organizationId}
        userName={session.user.name || ''}
        userImage={session.user.picture || ''}
      />
    </Box>
  );
}
