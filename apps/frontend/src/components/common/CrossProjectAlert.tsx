'use client';

import { useState } from 'react';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import EntityMessageState from '@/components/common/EntityMessageState';
import { ResolvedEntity } from '@/utils/api-client/resolve-client';
import { NotFoundEntityData } from '@/utils/entity-error-handler';
import {
  getResolveEntityIcon,
  SwapHorizOutlinedIcon,
} from '@/utils/entity-detail-icons';
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
  const EntityIcon = getResolveEntityIcon(entityData.table_name);

  const handleSwitch = () => {
    setSwitching(true);

    const targetProject = projects.find(
      p => String(p.id) === resolvedEntity.project_id
    );

    if (targetProject) {
      setActiveProject(targetProject);
      return;
    }

    const projectId = resolvedEntity.project_id;
    if (!projectId) {
      return;
    }

    writeActiveProjectId(projectId);
    window.location.reload();
  };

  if (switching) {
    return (
      <EntityMessageState
        icon={SwapHorizOutlinedIcon}
        title={`Switching to ${resolvedEntity.project_name}...`}
        description="Updating your active project."
        loading
      />
    );
  }

  return (
    <EntityMessageState
      icon={EntityIcon}
      title={`${displayName} is in another project`}
      description={`This ${displayName.toLowerCase()} belongs to project ${resolvedEntity.project_name}. Switch to that project to view it.`}
      primaryAction={{
        label: `Switch to ${resolvedEntity.project_name}`,
        onClick: handleSwitch,
        startIcon: <SwapHorizOutlinedIcon />,
        variant: 'contained',
      }}
      secondaryAction={{
        label: 'Back',
        onClick: () => window.history.back(),
        startIcon: <ArrowBackIcon />,
      }}
    />
  );
}
