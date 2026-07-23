'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { PlaygroundIcon } from '@/components/icons';
import { DeleteModal } from '@/components/common/DeleteModal';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { Fab, FabGroup } from '@/components/common/Fab';
import { useNotifications } from '@/components/common/NotificationContext';
import { useDeleteEndpoint } from '@/hooks/useEndpoints';
import { useEndpointDetailContext } from './EndpointDetailContext';

export default function EndpointHeaderActions() {
  const router = useRouter();
  const notifications = useNotifications();
  const { endpoint, duplicateEndpoint, isDuplicating } =
    useEndpointDetailContext();
  const deleteMutation = useDeleteEndpoint();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const handleDeleteConfirm = async () => {
    try {
      await deleteMutation.mutateAsync(endpoint.id);
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
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  return (
    <>
      <FabGroup>
        <Can capability={Capability.Playground.USE}>
          <Fab
            icon={<PlaygroundIcon />}
            tooltip="Playground"
            aria-label="Playground"
            onClick={() => router.push(`/playground?endpointId=${endpoint.id}`)}
            disabled={deleteMutation.isPending}
          />
        </Can>
        <Can capability={Capability.Endpoint.CREATE}>
          <Fab
            icon={<ContentCopyIcon />}
            tooltip="Duplicate"
            aria-label="Duplicate"
            onClick={duplicateEndpoint}
            loading={isDuplicating}
            disabled={deleteMutation.isPending}
          />
        </Can>
        <Can capability={Capability.Endpoint.DELETE}>
          <Fab
            icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
            tooltip="Delete endpoint"
            aria-label="Delete endpoint"
            onClick={() => setDeleteDialogOpen(true)}
            loading={deleteMutation.isPending}
          />
        </Can>
      </FabGroup>

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => !deleteMutation.isPending && setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
        title="Delete endpoint?"
        message={`Are you sure you want to delete "${endpoint.name}"? Don't worry, related data will not be deleted, only this record.`}
        itemType="endpoint"
      />
    </>
  );
}
