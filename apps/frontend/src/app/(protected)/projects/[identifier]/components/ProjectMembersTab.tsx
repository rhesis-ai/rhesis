'use client';

import * as React from 'react';
import { useCallback, useState } from 'react';
import { Button } from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { PersonAddIcon } from '@/components/icons';
import { Project, ProjectMember } from '@/utils/api-client/interfaces/project';
import ProjectMembers from './ProjectMembers';
import ProjectAddMemberDrawer from './ProjectAddMemberDrawer';

interface ProjectMembersTabProps {
  project: Project;
  projectId: string;
  sessionToken: string;
}

export default function ProjectMembersTab({
  project,
  projectId,
  sessionToken,
}: ProjectMembersTabProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [memberUserIds, setMemberUserIds] = useState<string[]>([]);

  const handleMembersLoaded = useCallback((members: ProjectMember[]) => {
    setMemberUserIds(members.map(m => m.user_id));
  }, []);

  const handleMemberAdded = useCallback(() => {
    setRefreshKey(key => key + 1);
  }, []);

  return (
    <>
      <SectionCard
        title="Members"
        actions={
          <Button
            variant="outlined"
            size="small"
            startIcon={<PersonAddIcon sx={{ fontSize: 20 }} />}
            onClick={() => setDrawerOpen(true)}
            sx={sectionEditButtonSx}
          >
            Add as member
          </Button>
        }
      >
        <ProjectMembers
          projectId={projectId}
          sessionToken={sessionToken}
          ownerId={project.owner_id ? String(project.owner_id) : undefined}
          refreshKey={refreshKey}
          onMembersLoaded={handleMembersLoaded}
        />
      </SectionCard>

      <ProjectAddMemberDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        projectId={projectId}
        sessionToken={sessionToken}
        memberUserIds={memberUserIds}
        onMemberAdded={handleMemberAdded}
      />
    </>
  );
}
