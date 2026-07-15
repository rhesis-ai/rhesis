'use client';

import * as React from 'react';
import {
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  alpha,
  useTheme,
  type SxProps,
  type Theme,
} from '@mui/material/styles';
import {
  GridColDef,
  GridRenderCellParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import GridBadge from '@/components/common/GridBadge';
import GridToolbar, {
  linkedDataGridRowSx,
  linkedGridToolbarSx,
  sectionCardGridBleedSx,
} from '@/components/common/GridToolbar';
import {
  ROW_ACTIONS_CLASS,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { experimentHref } from '@/utils/experiment-links';
import {
  BuiltInEnvironment,
  ExperimentRead,
  EnvironmentPointer,
  ProjectEnvironments as ProjectEnvironmentsShape,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { AddIcon, DeleteIcon, PromoteIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { DeleteModal } from '@/components/common/DeleteModal';
import ProjectAddEnvironmentDrawer from './ProjectAddEnvironmentDrawer';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { projectKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const FIGMA_BODY_SX = {
  fontSize: 14,
  lineHeight: '22px',
  color: (theme: { palette: { greyscale: { body: string } } }) =>
    theme.palette.greyscale.body,
} as const;

interface ProjectEnvironmentsProps {
  projectId: string;
  sessionToken: string;
  /** When true, the add action lives in the section header instead of the grid toolbar. */
  hideToolbarAddButton?: boolean;
}

export interface ProjectEnvironmentsHandle {
  openAddDrawer: () => void;
}

type EnvironmentRow = {
  name: string;
  pointer: EnvironmentPointer | null;
  isWellKnown: boolean;
};

interface EnvironmentsToolbarState {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
}

const EnvironmentsToolbarContext =
  React.createContext<EnvironmentsToolbarState>({
    searchQuery: '',
    setSearchQuery: () => {},
  });

function EnvironmentsToolbar() {
  const { searchQuery, setSearchQuery } = useContext(
    EnvironmentsToolbarContext
  );

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search environments…"
      searchWidth={288}
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
      sx={linkedGridToolbarSx}
    />
  );
}

function canRemoveEnvironment(row: EnvironmentRow): boolean {
  if (row.isWellKnown && !row.pointer) return false;
  return true;
}

/**
 * Project-scoped environments block.
 *
 * Always renders the {@link BuiltInEnvironment.ALL} names so the user
 * understands these names exist as first-class citizens even when no
 * experiment is bound. Bound and registered-but-unbound custom
 * environments appear inline alongside.
 *
 * Promoting an environment opens a drawer picker over the project's
 * shared experiments. Row delete is available from the actions column.
 */
export default forwardRef<ProjectEnvironmentsHandle, ProjectEnvironmentsProps>(
  function ProjectEnvironments(
    { projectId, sessionToken, hideToolbarAddButton = false },
    ref
  ) {
    const notifications = useNotifications();
    const theme = useTheme();
    const { status } = useSession();
    const canUpdateProject = useCan(Capability.Project.UPDATE);
    const [searchQuery, setSearchQuery] = useState('');

    const queryClient = useQueryClient();
    const environmentsQueryKey = [
      ...projectKeys.detail(projectId),
      'environments',
    ] as const;
    const [pickerEnvironmentName, setPickerEnvironmentName] = useState<
      string | null
    >(null);
    const [addDrawerOpen, setAddDrawerOpen] = useState(false);

    useImperativeHandle(ref, () => ({
      openAddDrawer: () => setAddDrawerOpen(true),
    }));

    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteTargetName, setDeleteTargetName] = useState<string | null>(
      null
    );
    const [deleting, setDeleting] = useState(false);

    const {
      data: envData,
      isLoading: loading,
      error: fetchError,
    } = useQuery({
      queryKey: environmentsQueryKey,
      queryFn: async () => {
        const client = new ApiClientFactory(sessionToken).getParametersClient();
        const [bindingsResp, expsResp] = await Promise.all([
          client.getEnvironments(projectId),
          client.listProjectExperiments(projectId, { limit: 200 }),
        ]);
        return { bindings: bindingsResp, experiments: expsResp };
      },
      enabled: isAuthenticated(status) && !!projectId,
    });

    const bindings = envData?.bindings ?? null;
    const experiments = envData?.experiments ?? [];
    const error =
      fetchError instanceof Error
        ? fetchError.message
        : fetchError
          ? 'Failed to load environments'
          : null;

    const refresh = useCallback(() => {
      queryClient.invalidateQueries({ queryKey: environmentsQueryKey });
    }, [queryClient, environmentsQueryKey]);

    const rows: EnvironmentRow[] = useMemo(() => {
      const out: EnvironmentRow[] = BuiltInEnvironment.ALL.map(name => ({
        name,
        pointer: bindings?.environments[name] ?? null,
        isWellKnown: true,
      }));
      if (bindings) {
        for (const [name, pointer] of Object.entries(bindings.environments)) {
          if (BuiltInEnvironment.ALL.includes(name)) continue;
          out.push({ name, pointer, isWellKnown: false });
        }
      }
      return out;
    }, [bindings]);

    const sharedExperiments = useMemo(
      () =>
        experiments.filter(
          e => e.visibility === 'shared' && e.versions_count > 0
        ),
      [experiments]
    );

    const experimentName = useCallback(
      (id: string) => experiments.find(e => e.id === id)?.name ?? id,
      [experiments]
    );

    const existingNames = useMemo(
      () =>
        new Set<string>([
          ...BuiltInEnvironment.ALL,
          ...Object.keys(bindings?.environments ?? {}),
        ]),
      [bindings]
    );

    const handleDeleteRow = useCallback((name: string) => {
      setDeleteTargetName(name);
      setDeleteDialogOpen(true);
    }, []);

    const handleConfirmRemove = useCallback(async () => {
      if (!deleteTargetName) return;
      setDeleting(true);
      try {
        const client = new ApiClientFactory(sessionToken).getParametersClient();
        await client.deleteEnvironment(projectId, deleteTargetName);
        refresh();
        setDeleteDialogOpen(false);
        setDeleteTargetName(null);
        notifications.show(`Environment "${deleteTargetName}" removed`, {
          severity: 'success',
        });
      } catch (e) {
        notifications.show(
          e instanceof Error ? e.message : 'Failed to remove environment',
          { severity: 'error' }
        );
      } finally {
        setDeleting(false);
      }
    }, [deleteTargetName, notifications, projectId, refresh, sessionToken]);

    const displayedRows = useMemo(() => {
      const query = searchQuery.trim().toLowerCase();
      if (!query) return rows;
      return rows.filter(row => {
        const experimentLabel = row.pointer
          ? experimentName(row.pointer.experiment_id).toLowerCase()
          : '';
        return (
          row.name.toLowerCase().includes(query) ||
          experimentLabel.includes(query) ||
          (row.pointer?.version ?? '').toLowerCase().includes(query)
        );
      });
    }, [rows, searchQuery, experimentName]);

    const columns: GridColDef<EnvironmentRow>[] = useMemo(
      () => [
        {
          field: 'name',
          headerName: 'Environment',
          flex: 1,
          minWidth: 160,
          sortable: false,
          renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
            const badge = <GridBadge label={params.row.name} />;
            if (!params.row.isWellKnown) return badge;
            return (
              <Tooltip
                title="Protected environment — always available, cannot be deleted."
                placement="top"
                arrow
              >
                {badge}
              </Tooltip>
            );
          },
        },
        {
          field: 'pointer',
          headerName: 'Bound to',
          flex: 1,
          minWidth: 160,
          sortable: false,
          renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
            if (!params.row.pointer) {
              return <Typography sx={FIGMA_BODY_SX}>Unbound</Typography>;
            }
            return (
              <Link
                href={experimentHref(
                  params.row.pointer.experiment_id,
                  params.row.pointer.version
                )}
                style={{ textDecoration: 'none' }}
              >
                <Typography
                  sx={{
                    ...FIGMA_BODY_SX,
                    color: 'primary.main',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  {experimentName(params.row.pointer.experiment_id)}
                </Typography>
              </Link>
            );
          },
        },
        {
          field: 'version',
          headerName: 'Version',
          width: 90,
          sortable: false,
          valueGetter: (_value, row) =>
            row.pointer ? shortVersion(row.pointer.version) : '',
          renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
            if (!params.row.pointer) return null;
            return (
              <GridBadge
                label={shortVersion(params.row.pointer.version)}
                sx={{ fontFamily: 'monospace' }}
              />
            );
          },
        },
        {
          field: 'status',
          headerName: 'Status',
          width: 90,
          sortable: false,
          valueGetter: (_value, row) => (row.pointer ? 'Bound' : 'Unbound'),
          renderCell: (params: GridRenderCellParams<EnvironmentRow>) => (
            <GridBadge label={params.row.pointer ? 'Bound' : 'Unbound'} />
          ),
        },
        {
          field: 'actions',
          headerName: '',
          width: 80,
          sortable: false,
          filterable: false,
          disableColumnMenu: true,
          align: 'center',
          headerAlign: 'center',
          renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
            const row = params.row;
            const promoteDisabled = sharedExperiments.length === 0;

            return (
              <Box
                className={ROW_ACTIONS_CLASS}
                sx={{
                  display: 'flex',
                  gap: '4px',
                  justifyContent: 'center',
                  alignItems: 'center',
                  width: '100%',
                }}
              >
                {canUpdateProject && (
                  <Tooltip
                    title={
                      promoteDisabled
                        ? 'No shared experiments to promote'
                        : 'Promote a shared experiment to this environment'
                    }
                  >
                    <span>
                      <IconButton
                        size="small"
                        disabled={promoteDisabled}
                        onClick={e => {
                          e.stopPropagation();
                          setPickerEnvironmentName(row.name);
                        }}
                        sx={{
                          p: 0.5,
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                            bgcolor: alpha(theme.palette.primary.main, 0.08),
                          },
                        }}
                        aria-label={`Promote experiment to ${row.name}`}
                      >
                        <PromoteIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </span>
                  </Tooltip>
                )}
                {canUpdateProject && canRemoveEnvironment(row) && (
                  <Tooltip title="Remove environment">
                    <IconButton
                      size="small"
                      onClick={e => {
                        e.stopPropagation();
                        handleDeleteRow(row.name);
                      }}
                      sx={{
                        p: 0.5,
                        color: 'text.secondary',
                        '&:hover': {
                          color: 'error.main',
                          bgcolor: alpha(theme.palette.error.main, 0.08),
                        },
                      }}
                      aria-label={`Remove environment ${row.name}`}
                    >
                      <DeleteIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            );
          },
        },
      ],
      [
        experimentName,
        sharedExperiments,
        theme,
        handleDeleteRow,
        canUpdateProject,
      ]
    );

    if (loading) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', p: 2, gap: 2 }}>
          <CircularProgress size={20} />
          <Typography color="text.secondary">
            Loading environments...
          </Typography>
        </Box>
      );
    }

    if (error) {
      return <Alert severity="error">{error}</Alert>;
    }

    return (
      <EnvironmentsToolbarContext.Provider
        value={{ searchQuery, setSearchQuery }}
      >
        <Box>
          <Box
            sx={
              [
                hideToolbarAddButton ? sectionCardGridBleedSx : null,
                rowActionsHoverSx,
              ].filter(Boolean) as SxProps<Theme>
            }
          >
            <BaseDataGrid
              rows={displayedRows}
              columns={columns}
              getRowId={row => row.name}
              loading={loading}
              toolbarSlot={EnvironmentsToolbar}
              showToolbar
              disablePaperWrapper
              pageSizeOptions={[10, 25, 50]}
              initialState={{
                pagination: {
                  paginationModel: { page: 0, pageSize: 10 },
                },
              }}
              sx={linkedDataGridRowSx}
            />
          </Box>

          {!hideToolbarAddButton && canUpdateProject ? (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => setAddDrawerOpen(true)}
              >
                New Environment
              </Button>
            </Box>
          ) : null}

          <DeleteModal
            open={deleteDialogOpen}
            onClose={() => {
              setDeleteDialogOpen(false);
              setDeleteTargetName(null);
            }}
            onConfirm={handleConfirmRemove}
            isLoading={deleting}
            title="Remove environment"
            message={
              <>
                <Typography sx={{ mb: 1.5 }}>
                  Remove &ldquo;{deleteTargetName}&rdquo;?
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  Only the pointer is cleared — the experiment and its version
                  history stay intact, and any past test runs that used this
                  name keep their snapshotted values.
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Built-in names ({BuiltInEnvironment.ALL.join(', ')}) stay
                  visible as Unbound; custom names disappear from the list.
                </Typography>
              </>
            }
            confirmButtonText="Remove"
            itemType="environment"
          />

          {pickerEnvironmentName && (
            <PromoteFromProjectDrawer
              open={!!pickerEnvironmentName}
              environmentName={pickerEnvironmentName}
              projectId={projectId}
              sessionToken={sessionToken}
              experiments={sharedExperiments}
              onClose={() => setPickerEnvironmentName(null)}
              onPromoted={async () => {
                setPickerEnvironmentName(null);
                await refresh();
              }}
            />
          )}

          <ProjectAddEnvironmentDrawer
            open={addDrawerOpen}
            onClose={() => setAddDrawerOpen(false)}
            projectId={projectId}
            sessionToken={sessionToken}
            existingNames={existingNames}
            onCreated={refresh}
          />
        </Box>
      </EnvironmentsToolbarContext.Provider>
    );
  }
);

interface PromoteFromProjectDrawerProps {
  open: boolean;
  environmentName: string;
  projectId: string;
  sessionToken: string;
  experiments: ExperimentRead[];
  onClose: () => void;
  onPromoted: () => void;
}

function PromoteFromProjectDrawer({
  open,
  environmentName,
  projectId,
  sessionToken,
  experiments,
  onClose,
  onPromoted,
}: PromoteFromProjectDrawerProps) {
  const notifications = useNotifications();
  const [experimentId, setExperimentId] = useState<string>(
    experiments[0]?.id ?? ''
  );
  const [version, setVersion] = useState<string>(
    experiments[0]?.latest_version ?? ''
  );
  const [submitting, setSubmitting] = useState(false);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const selectedExperiment = experiments.find(e => e.id === experimentId);

  // When the experiment changes, pull its versions list so the
  // version dropdown is accurate. We could pre-load all versions
  // for all experiments but it's cheaper to fetch on-demand.
  const [versions, setVersions] = useState<{ version: string }[]>([]);
  useEffect(() => {
    if (!experimentId) return;
    let cancelled = false;
    (async () => {
      try {
        const client = apiFactory.getParametersClient();
        const detail = await client.getExperiment(experimentId);
        if (cancelled) return;
        setVersions(detail.versions);
        setVersion(detail.versions[detail.versions.length - 1]?.version ?? '');
      } catch (_e) {
        // Best-effort; the dropdown just stays empty.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [experimentId, apiFactory]);

  const handleSubmit = async () => {
    if (!experimentId || !version) return;
    setSubmitting(true);
    try {
      const client = apiFactory.getParametersClient();
      await client.putEnvironment(projectId, environmentName, {
        experiment_id: experimentId,
        version,
      });
      notifications.show(
        `Environment "${environmentName}" now points at ${
          selectedExperiment?.name ?? experimentId
        } ${shortVersion(version)}`,
        { severity: 'success' }
      );
      onPromoted();
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to promote environment',
        { severity: 'error' }
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={`Promote to ${environmentName}`}
      onSave={handleSubmit}
      saveButtonText="Promote"
      saveDisabled={!experimentId || !version}
      loading={submitting}
    >
      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline="Binding"
          descriptiveText="Choose a shared experiment and version to bind this environment to."
        />
        <Box sx={drawerFieldsSx}>
          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Experiment (shared only)</InputLabel>
            <Select
              label="Experiment (shared only)"
              value={experimentId}
              onChange={e => setExperimentId(e.target.value)}
              notched
            >
              {experiments.map(e => (
                <MenuItem key={e.id} value={e.id}>
                  {e.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Version</InputLabel>
            <Select
              label="Version"
              value={versions.length === 0 ? '' : version}
              onChange={e => setVersion(e.target.value)}
              notched
            >
              {versions.length === 0 ? (
                <MenuItem value="" disabled>
                  Loading versions...
                </MenuItem>
              ) : (
                [...versions].reverse().map(v => (
                  <MenuItem key={v.version} value={v.version}>
                    {shortVersion(v.version)}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Box>
      </Box>
    </BaseDrawer>
  );
}
