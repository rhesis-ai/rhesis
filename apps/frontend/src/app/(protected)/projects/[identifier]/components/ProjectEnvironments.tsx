'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  BuiltInEnvironment,
  ENVIRONMENT_NAME_MAX_LENGTH,
  ExperimentRead,
  EnvironmentPointer,
  ProjectEnvironments as ProjectEnvironmentsShape,
  shortVersion,
  validateEnvironmentName,
} from '@/utils/api-client/interfaces/parameters';
import {
  CloseIcon,
  AddIcon,
  CheckIcon,
  DeleteIcon,
  PromoteIcon,
} from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';

interface ProjectEnvironmentsProps {
  projectId: string;
  sessionToken: string;
}

/** Sentinel id used by the in-grid "Add new environment" draft row. */
const DRAFT_ROW_ID = '__draft__';

type EnvironmentRow =
  | {
      name: string;
      pointer: EnvironmentPointer | null;
      isWellKnown: boolean;
      isDraft?: false;
    }
  | {
      name: typeof DRAFT_ROW_ID;
      isDraft: true;
    };

interface DraftState {
  /** Name being typed; trimmed at save time. */
  name: string;
}

/**
 * Project-scoped environments block.
 *
 * Always renders the {@link BuiltInEnvironment.ALL} names so the user
 * understands these names exist as first-class citizens even when no
 * experiment is bound. Bound and registered-but-unbound custom
 * environments appear inline alongside.
 *
 * Promoting an environment opens a small picker over the project's
 * shared experiments. Removing follows the application's standard
 * grid pattern: tick the rows you want gone and a "Remove N
 * environments" button surfaces in the toolbar, guarded by the same
 * {@link DeleteModal} used elsewhere. Well-known unbound rows aren't
 * selectable — they always exist as an overlay — but well-known bound
 * rows are (selecting "removes" the binding, which falls back to the
 * overlay-unbound state).
 */
export default function ProjectEnvironments({
  projectId,
  sessionToken,
}: ProjectEnvironmentsProps) {
  const notifications = useNotifications();

  const [bindings, setBindings] = useState<ProjectEnvironmentsShape | null>(
    null
  );
  const [experiments, setExperiments] = useState<ExperimentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pickerEnvironmentName, setPickerEnvironmentName] = useState<
    string | null
  >(null);
  const [picker, setPicker] = useState<{
    experimentId?: string;
    version?: string;
  }>({});

  // Inline "add new environment" state. Kept ``null`` when the user is
  // not adding, populated when the toolbar button is clicked. The
  // sentinel draft row is rendered iff ``draft !== null``. A new
  // environment registers without any experiment attached; the user
  // promotes onto it later from the regular row's Promote button.
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [savingDraft, setSavingDraft] = useState(false);

  // Bulk-removal state. Selection drives the toolbar Remove button,
  // mirroring the pattern in EndpointsGrid; deletion runs through the
  // shared ``DeleteModal`` so the confirmation UX is identical.
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const client = apiFactory.getParametersClient();
      const [bindingsResp, expsResp] = await Promise.all([
        client.getEnvironments(projectId),
        client.listProjectExperiments(projectId, { limit: 200 }),
      ]);
      setBindings(bindingsResp);
      setExperiments(expsResp);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load environments');
    } finally {
      setLoading(false);
    }
  }, [apiFactory, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

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
    if (draft) {
      // Draft sits at the top so the user's eye goes to the row they
      // just opened without having to scroll past built-in entries.
      out.unshift({ name: DRAFT_ROW_ID, isDraft: true });
    }
    return out;
  }, [bindings, draft]);

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

  // Only rows with something to delete are selectable. The four
  // built-in names that are *unbound* are pure overlay rows — there
  // is literally nothing to remove on the server — and the inline
  // draft row obviously can't be selected before it exists.
  const isRowSelectable = useCallback((params: GridRowParams) => {
    const row = params.row as EnvironmentRow;
    if (row.isDraft) return false;
    if (row.isWellKnown && !row.pointer) return false;
    return true;
  }, []);

  const selectedNames = useMemo(() => selectedRows.map(String), [selectedRows]);

  const handleBulkRemove = useCallback(async () => {
    if (selectedNames.length === 0) return;
    setDeleting(true);
    try {
      const client = apiFactory.getParametersClient();
      // Serial removal keeps a clean error story: the first failure
      // stops the loop and surfaces the underlying message verbatim.
      let next: ProjectEnvironmentsShape | null = null;
      for (const name of selectedNames) {
        next = await client.deleteEnvironment(projectId, name);
      }
      if (next) setBindings(next);
      setSelectedRows([]);
      setDeleteDialogOpen(false);
      notifications.show(
        selectedNames.length === 1
          ? `Environment "${selectedNames[0]}" removed`
          : `${selectedNames.length} environments removed`,
        { severity: 'success' }
      );
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to remove environments',
        { severity: 'error' }
      );
    } finally {
      setDeleting(false);
    }
  }, [apiFactory, projectId, selectedNames, notifications]);

  // --------------------------------------------------------------- //
  // Inline draft row plumbing                                       //
  // --------------------------------------------------------------- //

  // Combined name validation. Duplicates surface first because the
  // remediation ("use the Promote button on that row") is more
  // actionable than the generic shape hint.
  const draftNameError = useMemo<string | null>(() => {
    if (!draft) return null;
    const trimmed = draft.name.trim();
    if (!trimmed) return 'Name is required';
    if (existingNames.has(trimmed)) {
      return (
        `"${trimmed}" already exists — use the Promote button on ` +
        `that row to change what it points at.`
      );
    }
    return validateEnvironmentName(trimmed);
  }, [draft, existingNames]);

  const handleStartDraft = useCallback(() => {
    setDraft({ name: '' });
  }, []);

  const handleCancelDraft = useCallback(() => {
    setDraft(null);
  }, []);

  const handleSaveDraft = useCallback(async () => {
    if (!draft) return;
    const trimmed = draft.name.trim();
    if (draftNameError || !trimmed) {
      return;
    }
    setSavingDraft(true);
    try {
      const client = apiFactory.getParametersClient();
      const next = await client.registerEnvironment(projectId, {
        name: trimmed,
      });
      setBindings(next);
      notifications.show(
        `Environment "${trimmed}" created. Use Promote to bind it.`,
        { severity: 'success' }
      );
      setDraft(null);
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to create environment',
        { severity: 'error' }
      );
    } finally {
      setSavingDraft(false);
    }
  }, [apiFactory, projectId, draft, draftNameError, notifications]);

  const draftCanSave = !!draft && !draftNameError && !savingDraft;

  const columns: GridColDef<EnvironmentRow>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Environment',
        flex: 1,
        sortable: false,
        renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
          if (params.row.isDraft) {
            return (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  height: '100%',
                  width: '100%',
                  pr: 1,
                }}
              >
                <TextField
                  size="small"
                  fullWidth
                  autoFocus
                  placeholder="environment name"
                  value={draft?.name ?? ''}
                  onChange={e =>
                    setDraft(prev =>
                      prev ? { ...prev, name: e.target.value } : prev
                    )
                  }
                  onKeyDown={e => {
                    if (e.key === 'Enter' && draftCanSave) {
                      e.preventDefault();
                      handleSaveDraft();
                    } else if (e.key === 'Escape') {
                      e.preventDefault();
                      handleCancelDraft();
                    }
                  }}
                  error={!!draftNameError}
                  inputProps={{ maxLength: ENVIRONMENT_NAME_MAX_LENGTH }}
                />
              </Box>
            );
          }
          const chip = (
            <Chip
              size="small"
              label={params.row.name}
              color={params.row.pointer ? 'success' : 'default'}
              variant={params.row.pointer ? 'filled' : 'outlined'}
            />
          );
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                height: '100%',
              }}
            >
              {params.row.isWellKnown ? (
                <Tooltip
                  title="Protected environment — always available, cannot be deleted."
                  placement="top"
                  arrow
                >
                  {chip}
                </Tooltip>
              ) : (
                chip
              )}
            </Box>
          );
        },
      },
      {
        field: 'pointer',
        headerName: 'Bound to',
        flex: 2,
        sortable: false,
        renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
          if (params.row.isDraft) {
            return (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  height: '100%',
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  Unbound
                </Typography>
              </Box>
            );
          }
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                height: '100%',
              }}
            >
              {params.row.pointer ? (
                <>
                  <Link
                    href={`/experiments/${params.row.pointer.experiment_id}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <Typography
                      variant="body2"
                      color="primary"
                      sx={{ '&:hover': { textDecoration: 'underline' } }}
                    >
                      {experimentName(params.row.pointer.experiment_id)}
                    </Typography>
                  </Link>
                  <Chip
                    size="small"
                    label={shortVersion(params.row.pointer.version)}
                    sx={{ fontFamily: 'monospace' }}
                  />
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Unbound
                </Typography>
              )}
            </Box>
          );
        },
      },
      {
        field: 'actions',
        headerName: '',
        width: 160,
        sortable: false,
        filterable: false,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params: GridRenderCellParams<EnvironmentRow>) => {
          if (params.row.isDraft) {
            return (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: 0.5,
                  height: '100%',
                  width: '100%',
                }}
              >
                <Tooltip title={draftNameError ?? 'Create environment'}>
                  <span>
                    <IconButton
                      size="small"
                      color="primary"
                      onClick={handleSaveDraft}
                      disabled={!draftCanSave}
                      aria-label="Save new environment"
                    >
                      <CheckIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Cancel">
                  <IconButton
                    size="small"
                    onClick={handleCancelDraft}
                    aria-label="Cancel new environment"
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            );
          }
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 1,
                height: '100%',
                width: '100%',
              }}
            >
              <Tooltip
                title={
                  sharedExperiments.length === 0
                    ? 'No shared experiments to promote'
                    : 'Promote a shared experiment to this environment'
                }
              >
                <span>
                  <Button
                    size="small"
                    startIcon={<PromoteIcon />}
                    disabled={sharedExperiments.length === 0}
                    onClick={e => {
                      e.stopPropagation();
                      setPickerEnvironmentName(params.row.name);
                      setPicker({});
                    }}
                  >
                    Promote
                  </Button>
                </span>
              </Tooltip>
            </Box>
          );
        },
      },
    ],
    [
      experimentName,
      sharedExperiments,
      draft,
      draftNameError,
      draftCanSave,
      handleSaveDraft,
      handleCancelDraft,
    ]
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', p: 2, gap: 2 }}>
        <CircularProgress size={20} />
        <Typography color="text.secondary">Loading environments...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  const toolbar = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        width: '100%',
        gap: 2,
      }}
    >
      {/* Bulk action surfaces on the left only when rows are picked. */}
      {selectedNames.length > 0 ? (
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={() => setDeleteDialogOpen(true)}
          disabled={deleting}
        >
          Remove {selectedNames.length} environment
          {selectedNames.length > 1 ? 's' : ''}
        </Button>
      ) : (
        <Box />
      )}
      <Tooltip
        title={
          draft
            ? 'Finish the row being added first'
            : 'Add a new custom environment'
        }
      >
        <span>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            disabled={!!draft}
            onClick={handleStartDraft}
          >
            New Environment
          </Button>
        </span>
      </Tooltip>
    </Box>
  );

  return (
    <Box>
      {sharedExperiments.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No shared experiments yet. Create an experiment, save a version, and
          share it before promoting it onto an environment.
        </Alert>
      )}

      <Paper
        elevation={2}
        sx={{
          p: 2,
          // Rows in this grid aren't navigable on click — only the
          // per-row Promote button is interactive — so suppress the
          // "looks clickable" pointer cursor that BaseDataGrid applies
          // by default.
          '& .MuiDataGrid-row:hover': {
            cursor: 'default',
          },
        }}
      >
        <BaseDataGrid
          rows={rows}
          columns={columns}
          getRowId={row => row.name}
          density="comfortable"
          customToolbarContent={toolbar}
          checkboxSelection
          disableRowSelectionOnClick
          rowSelectionModel={selectedRows}
          onRowSelectionModelChange={setSelectedRows}
          isRowSelectable={isRowSelectable}
          disablePaperWrapper
          hideFooter
        />
      </Paper>

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleBulkRemove}
        isLoading={deleting}
        title={`Remove ${
          selectedNames.length > 1 ? 'environments' : 'environment'
        }`}
        message={
          <>
            <Typography sx={{ mb: 1.5 }}>
              {selectedNames.length === 1
                ? `Remove "${selectedNames[0]}"?`
                : `Remove ${selectedNames.length} environments?`}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Only the pointer
              {selectedNames.length > 1 ? 's are' : ' is'} cleared — the
              experiment{selectedNames.length > 1 ? 's' : ''} and{' '}
              {selectedNames.length > 1
                ? 'their version histories'
                : 'its version history'}{' '}
              stay intact, and any past test runs that used{' '}
              {selectedNames.length > 1 ? 'these names' : 'this name'} keep
              their snapshotted values.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Built-in names ({BuiltInEnvironment.ALL.join(', ')}) stay visible
              as Unbound; custom names disappear from the list.
            </Typography>
          </>
        }
        confirmButtonText="Remove"
        itemType={selectedNames.length > 1 ? 'environments' : 'environment'}
      />

      {pickerEnvironmentName && (
        <PromoteFromProjectDialog
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
    </Box>
  );
}

interface PromoteFromProjectDialogProps {
  open: boolean;
  environmentName: string;
  projectId: string;
  sessionToken: string;
  experiments: ExperimentRead[];
  onClose: () => void;
  onPromoted: () => void;
}

import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from '@mui/material';

function PromoteFromProjectDialog({
  open,
  environmentName,
  projectId,
  sessionToken,
  experiments,
  onClose,
  onPromoted,
}: PromoteFromProjectDialogProps) {
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
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Promote to {environmentName}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel>Experiment (shared only)</InputLabel>
            <Select
              label="Experiment (shared only)"
              value={experimentId}
              onChange={e => setExperimentId(e.target.value)}
            >
              {experiments.map(e => (
                <MenuItem key={e.id} value={e.id}>
                  {e.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth size="small">
            <InputLabel>Version</InputLabel>
            <Select
              label="Version"
              value={versions.length === 0 ? '' : version}
              onChange={e => setVersion(e.target.value)}
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
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!experimentId || !version || submitting}
        >
          {submitting ? 'Promoting...' : 'Promote'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
