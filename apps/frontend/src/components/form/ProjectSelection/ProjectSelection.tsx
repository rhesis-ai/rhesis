'use client';

import * as React from 'react';
import ProjectSelectionUI from './ProjectSelection.ui';
import { useProjectOptions } from './data/useProjectOptions';

export type ProjectSelectionContainerProps = {
  readonly isEditing: boolean;
  readonly projectId?: string | null;
  readonly onChange: (nextId: string | null) => void;
  readonly label: string;
  /** Show "None" / allow clearing */
  readonly allowUnset?: boolean;
};

export function ProjectSelection({
  isEditing,
  projectId,
                                   onChange,
  label,
  allowUnset = true,
}: ProjectSelectionContainerProps) {
  const { loading, options } = useProjectOptions();

  return (
    <ProjectSelectionUI
      isEditing={isEditing}
      loading={loading}
      options={options}
      value={projectId ?? null}
      onChange={onChange}
      label={label}
      allowUnset={allowUnset}
    />
  );
}
