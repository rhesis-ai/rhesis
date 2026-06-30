'use client';

import * as React from 'react';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FileCopyOutlinedIcon from '@mui/icons-material/FileCopyOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TrialDrawer from '../../components/TrialDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import { Fab, FabGroup } from '@/components/common/Fab';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { useRouter } from 'next/navigation';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface TestToTestSetProps {
  sessionToken: string;
  testId: string;
  parentButton?: React.ReactNode;
}

export default function TestToTestSet({
  sessionToken,
  testId,
  parentButton,
}: TestToTestSetProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const [trialDrawerOpen, setTrialDrawerOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isDuplicating, setIsDuplicating] = React.useState(false);

  const handleTrialSuccess = () => {
    setTrialDrawerOpen(false);
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      await apiFactory.getTestsClient().deleteTest(testId);
      notifications.show('Test deleted', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.push('/tests');
    } catch {
      notifications.show('Failed to delete test', {
        severity: 'error',
        autoHideDuration: 6000,
      });
      setIsDeleting(false);
    } finally {
      setDeleteDialogOpen(false);
    }
  };

  const handleDuplicate = async () => {
    setIsDuplicating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();
      const original = await testsClient.getTest(testId);
      const duplicate = await testsClient.createTest({
        prompt_id: original.prompt_id,
        behavior_id: original.behavior?.id,
        topic_id: original.topic?.id,
        category_id: original.category?.id,
        priority: original.priority,
        test_type_id: original.test_type?.id,
      });
      notifications.show('Test duplicated', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      router.push(`/tests/${duplicate.id}`);
    } catch {
      notifications.show('Failed to duplicate test', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDuplicating(false);
    }
  };

  return (
    <>
      <FabGroup>
        {parentButton}
        <Can capability={Capability.Test.DELETE}>
          <Fab
            icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
            tooltip="Delete test"
            onClick={() => setDeleteDialogOpen(true)}
            loading={isDeleting}
          />
        </Can>
        <Can capability={Capability.Test.CREATE}>
          <Fab
            icon={<FileCopyOutlinedIcon sx={{ fontSize: 28 }} />}
            tooltip="Duplicate test"
            onClick={handleDuplicate}
            loading={isDuplicating}
          />
        </Can>
        <Fab
          icon={<PlayArrowIcon sx={{ fontSize: 28 }} />}
          tooltip="Run test"
          onClick={() => setTrialDrawerOpen(true)}
        />
      </FabGroup>

      <TrialDrawer
        open={trialDrawerOpen}
        onClose={() => setTrialDrawerOpen(false)}
        sessionToken={sessionToken}
        testIds={[testId]}
        onSuccess={handleTrialSuccess}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => !isDeleting && setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete test?"
        message="This action cannot be undone. The test will be permanently removed."
      />
    </>
  );
}
