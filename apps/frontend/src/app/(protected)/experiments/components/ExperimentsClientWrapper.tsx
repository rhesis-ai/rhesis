'use client';

import React, { useMemo, useState } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { GridColDef } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { PageLayout } from '@/components/layout/PageLayout';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import {
  ExperimentRead,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { Capability } from '@/constants/capabilities';
import { can } from '@/utils/affordances';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { BiotechIcon } from '@/components/icons';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { experimentsList } from './list';
import CreateExperimentDialog from './CreateExperimentDialog';
import ExperimentFilterDrawer, {
  type ExperimentFilters,
  EMPTY_EXPERIMENT_FILTERS,
  countActiveExperimentFilters,
} from './ExperimentFilterDrawer';
import { formatDate } from '@/utils/date';

function toFilters(state: EntityGridFilterState<ExperimentFilters>) {
  return {
    search: state.search,
    visibility: state.drawer.visibility,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<ExperimentFilters> = {
  empty: EMPTY_EXPERIMENT_FILTERS,
  countActive: countActiveExperimentFilters,
  render: props => (
    <ExperimentFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

interface ExperimentsClientWrapperProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: ExperimentRead[];
  initialTotalCount?: number;
}

export default function ExperimentsClientWrapper({
  initialData,
  initialTotalCount,
}: ExperimentsClientWrapperProps) {
  const router = useRouter();
  const { activeProject } = useActiveProject();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Experiment.READ
  );
  const canCreateExperiment = useCan(Capability.Experiment.CREATE);
  const [createOpen, setCreateOpen] = useState(false);

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.2,
        minWidth: 160,
        filterable: true,
        renderCell: params => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BiotechIcon fontSize="small" color="action" />
            <Typography variant="body2">{params.row.name}</Typography>
          </Box>
        ),
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 1.8,
        minWidth: 200,
        filterable: false,
        sortable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary" noWrap>
            {params.value || '—'}
          </Typography>
        ),
      },
      {
        field: 'projectName',
        headerName: 'Project',
        flex: 0.9,
        minWidth: 120,
        filterable: true,
        sortable: false,
        valueGetter: (_value: unknown, row: ExperimentRead) =>
          row.project_name || '—',
      },
      {
        field: 'visibility',
        headerName: 'Visibility',
        flex: 0.6,
        minWidth: 90,
        filterable: true,
        type: 'singleSelect',
        valueOptions: ['private', 'shared'],
        renderCell: params => (
          <Chip
            size="small"
            label={params.value}
            color={params.value === 'shared' ? 'primary' : 'default'}
            variant="outlined"
          />
        ),
      },
      {
        field: 'latest_version',
        headerName: 'Latest',
        flex: 0.5,
        minWidth: 80,
        filterable: false,
        sortable: false,
        renderCell: params =>
          params.value ? (
            <Chip
              size="small"
              label={shortVersion(params.value)}
              sx={{ fontFamily: 'monospace' }}
            />
          ) : (
            <Typography variant="caption" color="text.disabled">
              —
            </Typography>
          ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 0.8,
        minWidth: 120,
        filterable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {params.value ? formatDate(params.value) : '—'}
          </Typography>
        ),
      },
    ],
    []
  );

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="experiments" />;

  return (
    <PageLayout
      title="Experiments"
      description="Experiments are named bundles of parameter values that can be pinned to test runs, ensuring reproducible and comparable executions across your project."
      actions={
        <FabGroup>
          <Can capability={Capability.Experiment.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="New Experiment"
              aria-label="New Experiment"
              onClick={() => setCreateOpen(true)}
              disabled={!activeProject}
            />
          </Can>
        </FabGroup>
      }
    >
      <EntityGrid<
        ExperimentRead,
        typeof experimentsList.filters,
        ExperimentFilters
      >
        descriptor={experimentsList}
        columns={columns}
        toFilters={toFilters}
        emptyState={
          <EntityEmptyState
            card
            icon={BiotechIcon}
            title="No experiments yet"
            description="Experiments let you bundle parameter values into versioned configurations. Create one to start tracking how different settings affect your test results."
            actionLabel={canCreateExperiment ? 'New Experiment' : undefined}
            onAction={
              canCreateExperiment ? () => setCreateOpen(true) : undefined
            }
            actionDisabled={!activeProject}
            enrichment={getEntityEmptyStateEnrichment('experiments')}
          />
        }
        initialData={initialData}
        initialTotalCount={initialTotalCount}
        searchPlaceholder="Search experiments…"
        drawer={drawerAdapter}
        getRowUrl={row => `/experiments/${row.id}`}
        editAction={{
          can: (row: ExperimentRead) => can(row, Capability.Experiment.UPDATE),
        }}
        pageSizeOptions={[10, 25, 50]}
        serverSort={false}
      />

      <CreateExperimentDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={async experiment => {
          setCreateOpen(false);
          router.push(`/experiments/${experiment.id}`);
        }}
      />
    </PageLayout>
  );
}
