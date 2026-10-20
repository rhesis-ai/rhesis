'use client';

import React from 'react';
import { FilterDrawerShell } from '@/components/common/FilterDrawer';
import ProjectSwitcherList from './ProjectSwitcherList';

interface ProjectSwitcherDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function ProjectSwitcherDrawer({
  open,
  onClose,
}: ProjectSwitcherDrawerProps) {
  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={onClose}
      resetLabel="Cancel"
      title="Switch project"
    >
      <ProjectSwitcherList onClose={onClose} />
    </FilterDrawerShell>
  );
}
