import { Box } from '@mui/material';
import { auth } from '@/auth';
import CreateProjectClient from './components/CreateProjectClient';
import { UUID } from 'crypto';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default async function CreateProjectPage() {
  const session = await auth();

  // Debug session information

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

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
      const apiFactory = new ApiClientFactory(session.session_token);
      const usersClient = apiFactory.getUsersClient();
      const userData = await usersClient.getUser(session.user.id);
      organizationId = userData.organization_id;
    } catch (_error) {}
  }

  return (
    <Box sx={{ p: 0 }}>
      <CreateProjectClient
        sessionToken={session.session_token}
        userId={session.user.id as UUID}
        organizationId={organizationId}
        userName={session.user.name || ''}
        userImage={session.user.picture || ''}
      />
    </Box>
  );
}
