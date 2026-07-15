'use client';

import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Box, Chip, Typography } from '@mui/material';
import {
  GridColDef,
  GridFilterModel,
  GridPaginationModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import GridToolbar from '@/components/common/GridToolbar';
import { DeleteModal } from '@/components/common/DeleteModal';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
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
import { useNotifications } from '@/components/common/NotificationContext';
import { combineExperimentFiltersToOData } from '@/utils/odata-filter';
import CreateExperimentDialog from './CreateExperimentDialog';
import { formatDate } from '@/utils/date';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

// ─── Toolbar context ───────────────────────────────────────────────────────────

interface ExperimentsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveFilters: boolean;
  activeFilterCount: number;
}

const ExperimentsToolbarContext = React.createContext<ExperimentsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveFilters: false,
  activeFilterCount: 0,
});

function ExperimentsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveFilters,
    activeFilterCount,
  } = useContext(ExperimentsToolbarContext);
  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search experiments…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveFilters}
      activeFilterCount={activeFilterCount}
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

// ─── Filter drawer ─────────────────────────────────────────────────────────────

const EMPTY_FILTERS = { visibility: '' };

function ExperimentsFilterDrawer({
  open,
  onClose,
  visibilityFilter,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  visibilityFilter: string;
  onApply: (visibility: string) => void;
}) {
  const committed = useMemo(
    () => ({ visibility: visibilityFilter }),
    [visibilityFilter]
  );
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    committed,
    EMPTY_FILTERS,
    f => onApply(f.visibility),
    onClose
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Visibility">
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {(['', 'private', 'shared'] as const).map(v => (
            <Box
              key={v || 'all'}
              component="button"
              onClick={() => setDraft(d => ({ ...d, visibility: v }))}
              sx={filterChipSx(draft.visibility === v)}
            >
              {v === '' ? 'All' : v.charAt(0).toUpperCase() + v.slice(1)}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}

interface ExperimentsClientWrapperProps {
  sessionToken: string;
}

export default function ExperimentsClientWrapper({
  sessionToken,
}: ExperimentsClientWrapperProps) {
  const isMounted = useRef(false);
  const router = useRouter();
  const { status } = useSession();
  const notifications = useNotifications();
  const { activeProject } = useActiveProject();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Experiment.READ
  );
  const canCreateExperiment = useCan(Capability.Experiment.CREATE);
  const [experiments, setExperiments] = useState<ExperimentRead[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [visibilityFilter, setVisibilityFilter] = useState<string>('');
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const initialLoadDone = useRef(false);

  const fetchExperiments = useCallback(
    async (skip: number, limit: number) => {
      if (!isAuthenticated(status)) return;

      try {
        // Only show loading overlay on the first load
        if (!initialLoadDone.current && isMounted.current) {
          setLoading(true);
        }

        const parametersClient = apiFactory.getParametersClient();
        const filterString = combineExperimentFiltersToOData(filterModel);

        const { data, totalCount: count } =
          await parametersClient.listExperiments({
            skip,
            limit,
            sort_by: 'created_at',
            sort_order: 'desc',
            ...(filterString && { filter: filterString }),
          });

        if (isMounted.current) {
          setExperiments(data);
          setTotalCount(count);
          initialLoadDone.current = true;
        }
      } catch {
        if (isMounted.current) {
          notifications.show('Failed to load experiments', {
            severity: 'error',
          });
          setExperiments([]);
        }
      } finally {
        if (isMounted.current) setLoading(false);
      }
    },
    [status, apiFactory, filterModel, notifications]
  );

  useEffect(() => {
    isMounted.current = true;

    const skip = paginationModel.page * paginationModel.pageSize;
    fetchExperiments(skip, paginationModel.pageSize);

    return () => {
      isMounted.current = false;
    };
  }, [paginationModel, fetchExperiments]);

  const handleFilterModelChange = useCallback(
    (newFilterModel: GridFilterModel) => {
      setFilterModel(newFilterModel);
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    []
  );

  // Sync search + visibility into the filter model
  useEffect(() => {
    setFilterModel(prev => {
      const items = [];
      if (searchQuery.trim()) {
        items.push({
          field: '__quickFilter__',
          operator: 'contains',
          value: searchQuery.trim(),
        });
      }
      if (visibilityFilter) {
        items.push({
          field: 'visibility',
          operator: 'equals',
          value: visibilityFilter,
        });
      }
      if (
        items.length === prev.items.length &&
        items.every((it, i) => it === prev.items[i])
      )
        return prev;
      return { items };
    });
    setPaginationModel(prev => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [searchQuery, visibilityFilter]);

  const handleDeleteExperiment = async () => {
    if (!deleteTargetId) return;
    setDeleting(true);
    try {
      const parametersClient = apiFactory.getParametersClient();
      await parametersClient.deleteExperiment(deleteTargetId);
      notifications.show('Experiment deleted', { severity: 'success' });
      setDeleteTargetId(null);
      fetchExperiments(
        paginationModel.page * paginationModel.pageSize,
        paginationModel.pageSize
      );
    } catch {
      notifications.show('Failed to delete experiment', { severity: 'error' });
    } finally {
      setDeleting(false);
    }
  };

  const columns: GridColDef[] = useMemo(
    () => [
      ...([
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
      ] as GridColDef[]),
      createRowActionsColumn({
        onEdit: id => router.push(`/experiments/${id}`),
        onDelete: id => setDeleteTargetId(id),
        canEdit: row =>
          can(row as unknown as ExperimentRead, Capability.Experiment.UPDATE),
        canDelete: row =>
          can(row as unknown as ExperimentRead, Capability.Experiment.DELETE),
        editTooltip: 'Open experiment',
        deleteTooltip: 'Delete experiment',
      }),
    ],
    [router]
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
      {!loading &&
      experiments.length === 0 &&
      !searchQuery.trim() &&
      !visibilityFilter ? (
        <EntityEmptyState
          card
          icon={BiotechIcon}
          title="No experiments yet"
          description="Experiments let you bundle parameter values into versioned configurations. Create one to start tracking how different settings affect your test results."
          actionLabel={canCreateExperiment ? 'New Experiment' : undefined}
          onAction={canCreateExperiment ? () => setCreateOpen(true) : undefined}
          actionDisabled={!activeProject}
          enrichment={getEntityEmptyStateEnrichment('experiments')}
        />
      ) : (
        <ExperimentsToolbarContext.Provider
          value={{
            searchQuery,
            setSearchQuery,
            openFilterDrawer: () => setFilterDrawerOpen(true),
            hasActiveFilters: !!visibilityFilter,
            activeFilterCount: visibilityFilter ? 1 : 0,
          }}
        >
          <BaseDataGrid
            rows={experiments}
            columns={columns}
            loading={loading}
            linkPath="/experiments"
            linkField="id"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            filterModel={filterModel}
            onFilterModelChange={handleFilterModelChange}
            serverSideFiltering={true}
            serverSidePagination={true}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
            showToolbar={true}
            toolbarSlot={ExperimentsUnifiedToolbar}
            persistState
            sx={rowActionsHoverSx}
          />
        </ExperimentsToolbarContext.Provider>
      )}

      <CreateExperimentDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        sessionToken={sessionToken}
        onCreated={async experiment => {
          setCreateOpen(false);
          router.push(`/experiments/${experiment.id}`);
        }}
      />

      <ExperimentsFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        visibilityFilter={visibilityFilter}
        onApply={v => setVisibilityFilter(v)}
      />

      <DeleteModal
        open={!!deleteTargetId}
        onClose={() => setDeleteTargetId(null)}
        onConfirm={handleDeleteExperiment}
        isLoading={deleting}
        title="Delete Experiment"
        message="Are you sure you want to delete this experiment? This action cannot be undone."
        itemType="experiment"
      />
    </PageLayout>
  );
}
