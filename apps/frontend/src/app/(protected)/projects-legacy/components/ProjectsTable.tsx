'use client';

import React, { ReactNode } from 'react';
import { Chip, Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import BaseTable from '@/components/common/BaseTable';
import { Project } from '@/utils/api-client/interfaces/project';
import AddIcon from '@mui/icons-material/Add';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';

interface ProjectsTableProps {
  projects: Project[];
}

interface Column {
  id: string;
  label: string;
  render: (project: Project) => ReactNode;
}

const getEnvironmentColor = (environment: string | undefined) => {
  if (!environment) return 'default';
  
  switch (environment.toLowerCase()) {
    case 'production':
      return 'success';
    case 'staging':
      return 'warning';
    case 'development':
      return 'info';
    default:
      return 'default';
  }
};

export default function ProjectsTable({ projects }: ProjectsTableProps) {
  const router = useRouter();

  const handleRowClick = (project: Project) => {
    router.push(`/projects-legacy/${project.id}`);
  };

  const columns: Column[] = [
    {
      id: 'name',
      label: 'Name',
      render: (project: Project) => project.name,
    },
    {
      id: 'description',
      label: 'Description',
      render: (project: Project) => project.description,
    },
    {
      id: 'environment',
      label: 'Environment',
      render: (project: Project) => (
        <Chip
          label={project.environment}
          size="small"
          variant="outlined"
          color={getEnvironmentColor(project.environment)}
        />
      ),
    },
    {
      id: 'useCase',
      label: 'Use Case',
      render: (project: Project) => (
        <Chip
          label={project.useCase}
          size="small"
          variant="outlined"
          color="primary"
        />
      ),
    },
    {
      id: 'owner',
      label: 'Owner',
      render: (project: Project) => project.owner?.name || 'Unknown',
    },
    {
      id: 'tags',
      label: 'Tags',
      render: (project: Project) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {project.tags?.map((tag) => (
            <Chip
              key={tag}
              label={tag}
              size="small"
              variant="outlined"
              color="secondary"
            />
          ))}
        </Box>
      ),
    },
  ];

  return (
    <BaseTable
      columns={columns}
      data={projects}
      onRowClick={handleRowClick}
      actionButtons={[
        {
          label: "New Project",
          href: "/projects-legacy/new",
          icon: <AddIcon />,
          variant: "outlined"
        },
        {
          label: "Project Wizard",
          href: "/projects-legacy/wizard",
          icon: <AutoFixHighIcon />,
          variant: "contained"
        }
      ]}
    />
  );
} 