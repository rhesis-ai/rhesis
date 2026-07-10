'use client';

import { useState } from 'react';
import { Alert, Button, Box, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import SwapHorizIcon from '@mui/icons-material/SwapHorizOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { ResolvedEntity } from '@/utils/api-client/resolve-client';
import { NotFoundEntityData } from '@/utils/entity-error-handler';
import { writeActiveProjectId } from '@/utils/active-project';

interface CrossProjectAlertProps {
  resolvedEntity: ResolvedEntity;
  entityData: NotFoundEntityData;
  backUrl?: string;
  backLabel?: string;
}

export function CrossProjectAlert({
  resolvedEntity,
  entityData,
}: CrossProjectAlertProps) {
  const { projects, setActiveProject } = useActiveProject();
  const [switching, setSwitching] = useState(false);

  const displayName =
    entityData.model_name_display || entityData.model_name || 'item';

  if (resolvedEntity.resolution === 'no_access') {
    return (
      <Alert severity="warning" icon={<LockOutlinedIcon />}>
        <Box mb={2}>
          <Typography>
            This {displayName.toLowerCase()} belongs to a project you don't have
            access to. Contact your administrator to request access.
          </Typography>
        </Box>

        <Box display="flex" gap={2} flexWrap="wrap">
          <Button
            variant="outlined"
            size="medium"
            startIcon={<ArrowBackIcon />}
            onClick={() => window.history.back()}
          >
            Back
          </Button>
        </Box>
      </Alert>
    );
  }

  const handleSwitch = () => {
    setSwitching(true);

    const targetProject = projects.find(
      p => String(p.id) === resolvedEntity.project_id
    );

    if (targetProject) {
      setActiveProject(targetProject);
      return;
    }

    writeActiveProjectId(resolvedEntity.project_id!);
    window.location.reload();
  };

  if (switching) {
    return (
      <Alert severity="info">
        <Typography>
          Switching to <strong>{resolvedEntity.project_name}</strong>...
        </Typography>
      </Alert>
    );
  }

  return (
    <Alert severity="info">
      <Box mb={2}>
        <Typography>
          This {displayName.toLowerCase()} belongs to project{' '}
          <strong>{resolvedEntity.project_name}</strong>. Switch to that project
          to view it.
        </Typography>
      </Box>

      <Box display="flex" gap={2} flexWrap="wrap">
        <Button
          variant="contained"
          size="medium"
          startIcon={<SwapHorizIcon />}
          onClick={handleSwitch}
        >
          Switch to {resolvedEntity.project_name}
        </Button>
        <Button
          variant="outlined"
          size="medium"
          startIcon={<ArrowBackIcon />}
          onClick={() => window.history.back()}
        >
          Back
        </Button>
      </Box>
    </Alert>
  );
}
