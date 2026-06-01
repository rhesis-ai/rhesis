'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useSession } from 'next-auth/react';
import { PlaygroundIcon } from '@/components/icons';
import { DeleteModal } from '@/components/common/DeleteModal';
import { Fab, FabGroup } from '@/components/common/Fab';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useEndpointDetailContext } from './EndpointDetailContext';

export default function EndpointHeaderActions() {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();
  const { endpoint, duplicateEndpoint, isDuplicating } =
    useEndpointDetailContext();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteConfirm = async () => {
    const sessionToken = session?.session_token;
    if (!sessionToken) return;

    setIsDeleting(true);
    try {
      const factory = new ApiClientFactory(sessionToken);
      await factory.getEndpointsClient().deleteEndpoint(endpoint.id);
      notifications.show('Endpoint deleted', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      if (endpoint.project_id) {
        router.push(`/projects/${endpoint.project_id}`);
      } else {
        router.push('/endpoints');
      }
    } catch {
      notifications.show('Failed to delete endpoint', {
        severity: 'error',
        autoHideDuration: 6000,
      });
      setIsDeleting(false);
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  return (
    <>
      <FabGroup>
        <Fab
          icon={<PlaygroundIcon />}
          tooltip="Playground"
          aria-label="Playground"
          onClick={() => router.push(`/playground?endpointId=${endpoint.id}`)}
          disabled={isDeleting}
        />
        <Fab
          icon={<ContentCopyIcon />}
          tooltip="Duplicate"
          aria-label="Duplicate"
          onClick={duplicateEndpoint}
          loading={isDuplicating}
          disabled={isDeleting}
        />
        <Fab
          icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
          tooltip="Delete endpoint"
          aria-label="Delete endpoint"
          onClick={() => setDeleteDialogOpen(true)}
          loading={isDeleting}
        />
      </FabGroup>

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => !isDeleting && setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete endpoint?"
        message={`Are you sure you want to delete "${endpoint.name}"? Don't worry, related data will not be deleted, only this record.`}
        itemType="endpoint"
      />
    </>
  );
}
