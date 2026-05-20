'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import CheckIcon from '@mui/icons-material/Check';
import { AddIcon, BiotechIcon, EditIcon, SaveIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentDetail,
  ExperimentRead,
  ExperimentVersion,
  ParameterSchema,
  ParameterValue,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import TypedValueEditor, {
  renderValuePreview,
} from '@/app/(protected)/experiments/[identifier]/components/TypedValueEditor';
import { TYPE_META } from '@/app/(protected)/projects/[identifier]/components/parameter-schema-shared';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import type { SelectedExperiment } from '@/utils/test-run-batch';

interface SelectExperimentsDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (experiments: SelectedExperiment[]) => void;
  sessionToken: string;
  projectId: string | null;
  initialSelection?: SelectedExperiment[];
  title?: string;
  subtitle?: string;
}

interface SelectedRow extends SelectedExperiment {
  experiment_id: string;
}

function rowKey(experimentId: string, version: string): string {
  return `${experimentId}::${version}`;
}

/** Drop duplicate version hashes while preserving append order. */
function dedupeVersionsByHash(
  versions: ExperimentVersion[]
): ExperimentVersion[] {
  const seen = new Set<string>();
  const out: ExperimentVersion[] = [];
  for (let i = versions.length - 1; i >= 0; i--) {
    const v = versions[i];
    if (seen.has(v.version)) continue;
    seen.add(v.version);
    out.unshift(v);
  }
  return out;
}

/**
 * Multi-experiment picker dialog.
 *
 * Supports selecting multiple versions from the same experiment —
 * each selected (experiment, version) pair produces its own test run.
 * The version dropdown previews values; a separate "Add this version"
 * button adds the previewed version to the selection.
 */
export default function SelectExperimentsDialog({
  open,
  onClose,
  onConfirm,
  sessionToken,
  projectId,
  initialSelection = [],
  title = 'Add Experiments',
  subtitle = 'Pick one or more experiment versions to run. Each selected version triggers its own run.',
}: SelectExperimentsDialogProps) {
  const notifications = useNotifications();
  const searchRef = React.useRef<HTMLInputElement>(null);

  const [experiments, setExperiments] = React.useState<ExperimentRead[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [searchQuery, setSearchQuery] = React.useState('');

  const [selectedRows, setSelectedRows] = React.useState<SelectedRow[]>([]);
  const [focusedId, setFocusedId] = React.useState<string | null>(null);
  const [viewedVersionHash, setViewedVersionHash] = React.useState<
    string | null
  >(null);

  const [detail, setDetail] = React.useState<ExperimentDetail | null>(null);
  const [schema, setSchema] = React.useState<ParameterSchema | null>(null);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [detailError, setDetailError] = React.useState<string | null>(null);

  const [editMode, setEditMode] = React.useState(false);
  const [draftValues, setDraftValues] = React.useState<
    Record<string, ParameterValue | null>
  >({});
  const [draftMessage, setDraftMessage] = React.useState('');
  const [savingVersion, setSavingVersion] = React.useState(false);

  const apiFactory = React.useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  React.useEffect(() => {
    if (!open) return;
    setSearchQuery('');
    setSelectedRows(
      initialSelection.map(row => ({
        experiment_id: String(row.experiment_id),
        experiment_name: row.experiment_name,
        version: row.version,
      }))
    );
    setFocusedId(
      initialSelection.length > 0
        ? String(initialSelection[0].experiment_id)
        : null
    );
    setViewedVersionHash(null);
    setEditMode(false);
    setDraftValues({});
    setDraftMessage('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  React.useEffect(() => {
    if (!open || !projectId) return;
    let cancelled = false;
    const fetchExperiments = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const client = apiFactory.getParametersClient();
        const exps = await client.listProjectExperiments(projectId, {
          limit: 200,
        });
        if (cancelled) return;
        setExperiments(exps.filter(e => e.latest_version));
      } catch (err) {
        if (cancelled) return;
        setLoadError(getApiErrorMessage(err, 'Failed to load experiments'));
        setExperiments([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchExperiments();
    return () => {
      cancelled = true;
    };
  }, [apiFactory, open, projectId]);

  const filteredExperiments = React.useMemo(() => {
    if (!searchQuery.trim()) return experiments;
    const q = searchQuery.toLowerCase();
    return experiments.filter(
      exp =>
        exp.name.toLowerCase().includes(q) ||
        (exp.description ?? '').toLowerCase().includes(q) ||
        exp.visibility.toLowerCase().includes(q)
    );
  }, [experiments, searchQuery]);

  React.useEffect(() => {
    if (!open || !focusedId) {
      setDetail(null);
      setSchema(null);
      return;
    }
    let cancelled = false;
    const loadDetail = async () => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const client = apiFactory.getParametersClient();
        const exp = await client.getExperiment(focusedId);
        if (cancelled) return;
        setDetail(exp);
        const schemaResp = await client.getSchema(exp.project_id);
        if (cancelled) return;
        setSchema(schemaResp);
      } catch (err) {
        if (cancelled) return;
        setDetailError(
          getApiErrorMessage(err, 'Failed to load experiment detail')
        );
        setDetail(null);
        setSchema(null);
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    };
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [apiFactory, focusedId, open]);

  React.useEffect(() => {
    setEditMode(false);
    setDraftValues({});
    setDraftMessage('');
    setViewedVersionHash(null);
  }, [focusedId]);

  const detailVersions = React.useMemo(
    () => dedupeVersionsByHash(detail?.versions ?? []),
    [detail?.versions]
  );

  const latestVersionHash = React.useMemo(() => {
    if (!detail) return null;
    if (detail.latest_version) return detail.latest_version;
    return detailVersions.at(-1)?.version ?? null;
  }, [detail, detailVersions]);

  const effectiveViewedVersion = viewedVersionHash ?? latestVersionHash ?? null;

  const focusedSelectedVersions = React.useMemo(
    () =>
      focusedId
        ? selectedRows.filter(row => row.experiment_id === focusedId)
        : [],
    [selectedRows, focusedId]
  );

  const isViewedVersionSelected = React.useMemo(
    () =>
      !!effectiveViewedVersion &&
      focusedSelectedVersions.some(
        row => row.version === effectiveViewedVersion
      ),
    [effectiveViewedVersion, focusedSelectedVersions]
  );

  const focusedVersion: ExperimentVersion | null = React.useMemo(() => {
    if (!detail || !effectiveViewedVersion) return null;
    return (
      detailVersions.find(v => v.version === effectiveViewedVersion) ?? null
    );
  }, [detail, detailVersions, effectiveViewedVersion]);

  const getSelectedVersionCount = React.useCallback(
    (experimentId: string) =>
      selectedRows.filter(row => row.experiment_id === experimentId).length,
    [selectedRows]
  );

  const addVersionToSelection = React.useCallback(
    (experimentId: string, experimentName: string, version: string) => {
      setSelectedRows(prev => {
        if (
          prev.some(
            row => row.experiment_id === experimentId && row.version === version
          )
        ) {
          return prev;
        }
        return [
          ...prev,
          {
            experiment_id: experimentId,
            experiment_name: experimentName,
            version,
          },
        ];
      });
    },
    []
  );

  const removeVersion = React.useCallback(
    (experimentId: string, version: string) => {
      setSelectedRows(prev =>
        prev.filter(
          row =>
            !(row.experiment_id === experimentId && row.version === version)
        )
      );
    },
    []
  );

  const removeAllVersions = React.useCallback((experimentId: string) => {
    setSelectedRows(prev =>
      prev.filter(row => row.experiment_id !== experimentId)
    );
  }, []);

  const startEditing = React.useCallback(() => {
    if (!schema) return;
    const seeded: Record<string, ParameterValue | null> = {};
    for (const field of schema.fields) {
      const fromVersion = focusedVersion?.values[field.name];
      if (fromVersion !== undefined) {
        seeded[field.name] = fromVersion as ParameterValue;
      } else {
        seeded[field.name] = field.default ?? null;
      }
    }
    setDraftValues(seeded);
    setDraftMessage('');
    setEditMode(true);
  }, [focusedVersion, schema]);

  const cancelEditing = React.useCallback(() => {
    setEditMode(false);
    setDraftValues({});
    setDraftMessage('');
  }, []);

  const handleSaveNewVersion = React.useCallback(async () => {
    if (!detail || !schema) return;
    setSavingVersion(true);
    try {
      const payloadValues: Record<string, unknown> = {};
      for (const [name, value] of Object.entries(draftValues)) {
        if (value !== null) payloadValues[name] = value;
      }
      const client = apiFactory.getParametersClient();
      const newVersion = await client.createExperimentVersion(detail.id, {
        values: payloadValues,
        message: draftMessage.trim() || undefined,
        parent_version: detail.latest_version ?? undefined,
      });
      const refreshed = await client.getExperiment(detail.id);
      setDetail(refreshed);
      setEditMode(false);
      setDraftValues({});
      setDraftMessage('');
      const versionToSelect = refreshed.latest_version ?? newVersion.version;
      addVersionToSelection(detail.id, refreshed.name, versionToSelect);
      setViewedVersionHash(versionToSelect);
      setExperiments(prev =>
        prev.map(exp =>
          exp.id === detail.id
            ? {
                ...exp,
                latest_version: refreshed.latest_version,
                versions_count: refreshed.versions_count,
              }
            : exp
        )
      );
      notifications.show('Version saved and added to selection', {
        severity: 'success',
      });
    } catch (err) {
      notifications.show(getApiErrorMessage(err, 'Failed to save version'), {
        severity: 'error',
      });
    } finally {
      setSavingVersion(false);
    }
  }, [
    addVersionToSelection,
    apiFactory,
    detail,
    draftMessage,
    draftValues,
    notifications,
    schema,
  ]);

  const handleConfirm = React.useCallback(() => {
    onConfirm(
      selectedRows.map(row => ({
        experiment_id: row.experiment_id,
        experiment_name: row.experiment_name,
        version: row.version,
      }))
    );
    onClose();
  }, [onClose, onConfirm, selectedRows]);

  const renderDetailPane = () => {
    if (!focusedId) {
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: 4,
            height: '100%',
            textAlign: 'center',
          }}
        >
          <Typography color="text.secondary" variant="body2">
            Pick an experiment on the left to view its details, edit values, and
            add versions to the run.
          </Typography>
        </Box>
      );
    }

    if (detailLoading) {
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            p: 4,
            gap: 1,
          }}
        >
          <CircularProgress size={20} />
          <Typography color="text.secondary">Loading experiment...</Typography>
        </Box>
      );
    }

    if (detailError) {
      return (
        <Alert severity="error" sx={{ m: 2 }}>
          {detailError}
        </Alert>
      );
    }

    if (!detail || !schema) {
      return null;
    }

    const hasFocusedVersions = focusedSelectedVersions.length > 0;

    return (
      <Stack
        spacing={2}
        sx={{
          p: 2,
          overflowY: 'auto',
          maxHeight: theme => theme.spacing(72),
        }}
      >
        <Stack
          direction="row"
          spacing={1}
          alignItems="flex-start"
          justifyContent="space-between"
        >
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <BiotechIcon fontSize="small" color="primary" />
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap>
                {detail.name}
              </Typography>
              <Tooltip title="Open experiment in a new tab">
                <IconButton
                  component={Link}
                  href={`/experiments/${detail.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="small"
                >
                  <OpenInNewIcon fontSize="inherit" />
                </IconButton>
              </Tooltip>
            </Stack>
            {detail.description && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 0.5 }}
              >
                {detail.description}
              </Typography>
            )}
            <Stack direction="row" spacing={0.5} sx={{ mt: 1 }}>
              <Chip
                size="small"
                variant="outlined"
                label={detail.visibility}
                color={detail.visibility === 'shared' ? 'primary' : 'default'}
              />
              <Chip
                size="small"
                variant="outlined"
                label={`${detailVersions.length} version${
                  detailVersions.length === 1 ? '' : 's'
                }`}
              />
            </Stack>
          </Box>
        </Stack>

        <Divider />

        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          alignItems={{ xs: 'stretch', sm: 'center' }}
          justifyContent="space-between"
        >
          <FormControl size="small" sx={{ minWidth: 200, flex: 1 }}>
            <InputLabel>Version</InputLabel>
            <Select
              label="Version"
              value={effectiveViewedVersion ?? ''}
              onChange={e => {
                setViewedVersionHash(e.target.value as string);
              }}
              disabled={editMode || detailVersions.length === 0}
            >
              {[...detailVersions].reverse().map(ver => (
                <MenuItem key={ver.version} value={ver.version}>
                  <Stack
                    direction="row"
                    spacing={1}
                    alignItems="center"
                    sx={{ width: '100%' }}
                  >
                    <Typography variant="body2">
                      {shortVersion(ver.version)}
                    </Typography>
                    {latestVersionHash && ver.version === latestVersionHash && (
                      <Chip
                        size="small"
                        label="latest"
                        color="primary"
                        variant="outlined"
                      />
                    )}
                    {selectedRows.some(
                      row =>
                        row.experiment_id === detail.id &&
                        row.version === ver.version
                    ) && <CheckIcon fontSize="small" color="success" />}
                    {ver.message && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {ver.message}
                      </Typography>
                    )}
                  </Stack>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {isViewedVersionSelected ? (
            <Button
              variant="outlined"
              size="small"
              color="success"
              startIcon={<CheckIcon />}
              onClick={() => {
                if (effectiveViewedVersion) {
                  removeVersion(detail.id, effectiveViewedVersion);
                }
              }}
              sx={{ height: 40 }}
            >
              Added
            </Button>
          ) : (
            <Button
              variant="contained"
              size="small"
              onClick={() => {
                if (effectiveViewedVersion) {
                  addVersionToSelection(
                    detail.id,
                    detail.name,
                    effectiveViewedVersion
                  );
                }
              }}
              disabled={!effectiveViewedVersion || editMode}
              startIcon={<AddIcon />}
              sx={{ height: 40 }}
            >
              Add
            </Button>
          )}
          {!editMode ? (
            <Button
              size="small"
              startIcon={<EditIcon />}
              onClick={startEditing}
              disabled={schema.fields.length === 0}
            >
              Edit values
            </Button>
          ) : (
            <Button
              size="small"
              color="inherit"
              onClick={cancelEditing}
              disabled={savingVersion}
            >
              Cancel edit
            </Button>
          )}
        </Stack>

        {hasFocusedVersions && (
          <Box>
            <Stack
              direction="row"
              spacing={0.5}
              alignItems="center"
              sx={{ flexWrap: 'wrap', rowGap: 0.5 }}
            >
              <Typography variant="caption" color="text.secondary">
                In run:
              </Typography>
              {focusedSelectedVersions.map(row => (
                <Chip
                  key={rowKey(row.experiment_id, row.version)}
                  size="small"
                  variant="outlined"
                  color="default"
                  label={shortVersion(row.version)}
                  onClick={() => setViewedVersionHash(row.version)}
                  onDelete={() => removeVersion(row.experiment_id, row.version)}
                  deleteIcon={<CloseIcon />}
                />
              ))}
              {focusedSelectedVersions.length > 1 && (
                <Button
                  size="small"
                  color="inherit"
                  sx={{ fontSize: '0.7rem', minWidth: 'auto', px: 0.5 }}
                  onClick={() => removeAllVersions(detail.id)}
                >
                  Clear all
                </Button>
              )}
            </Stack>
          </Box>
        )}

        {schema.fields.length === 0 ? (
          <Alert severity="info">
            This project has no parameter schema yet. Define one on the project
            page before editing values here.
          </Alert>
        ) : !editMode ? (
          <Stack spacing={1}>
            {schema.fields.map(field => {
              const value = focusedVersion?.values[field.name] ?? null;
              const typeMeta = TYPE_META[field.type];
              const TypeIcon = typeMeta.icon;
              const typeIconColor =
                typeMeta.color === 'default' ? 'action' : typeMeta.color;
              return (
                <Box
                  key={field.name}
                  sx={{
                    p: 1.5,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: theme => theme.shape.borderRadius,
                  }}
                >
                  <Stack
                    direction="row"
                    spacing={1}
                    alignItems="center"
                    sx={{ mb: 0.5 }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {field.name}
                    </Typography>
                    <Tooltip title={typeMeta.label}>
                      <TypeIcon fontSize="small" color={typeIconColor} />
                    </Tooltip>
                    {field.required && (
                      <Chip
                        size="small"
                        variant="outlined"
                        color="warning"
                        label="required"
                      />
                    )}
                  </Stack>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ wordBreak: 'break-word' }}
                  >
                    {renderValuePreview(value)}
                  </Typography>
                </Box>
              );
            })}
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Alert severity="info">
              Saving writes a new version on this experiment and adds it to the
              selection. Identical values are a no-op on the server.
            </Alert>
            {schema.fields.map(field => (
              <TypedValueEditor
                key={field.name}
                field={field}
                value={draftValues[field.name] ?? null}
                onChange={value =>
                  setDraftValues(prev => ({ ...prev, [field.name]: value }))
                }
              />
            ))}
            <TextField
              label="Message (optional)"
              placeholder="Describe what changed"
              value={draftMessage}
              onChange={e => setDraftMessage(e.target.value)}
              size="small"
              fullWidth
              disabled={savingVersion}
            />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSaveNewVersion}
                disabled={savingVersion}
              >
                {savingVersion ? 'Saving...' : 'Save as new version'}
              </Button>
            </Box>
          </Stack>
        )}
      </Stack>
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      TransitionProps={{ onEntered: () => searchRef.current?.focus() }}
      PaperProps={{ sx: { maxHeight: '95vh' } }}
    >
      <DialogTitle>
        <Typography variant="h6" component="div">
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {subtitle}
        </Typography>
      </DialogTitle>

      <DialogContent
        dividers
        sx={{
          p: 0,
          overflow: 'hidden',
          minHeight: theme => theme.spacing(60),
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            maxHeight: theme => theme.spacing(74),
            minHeight: theme => theme.spacing(60),
          }}
        >
          <Box
            sx={{
              width: { xs: '100%', md: 360 },
              borderRight: { md: '1px solid' },
              borderBottom: { xs: '1px solid', md: 'none' },
              borderColor: { md: 'divider', xs: 'divider' },
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
            }}
          >
            <Box sx={{ p: 2 }}>
              <TextField
                fullWidth
                placeholder="Search experiments..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                inputRef={searchRef}
                size="small"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            <Box
              sx={{
                flex: 1,
                overflowY: 'auto',
                px: 2,
                pb: 2,
                maxHeight: theme => theme.spacing(66),
              }}
            >
              {!projectId ? (
                <Typography
                  color="text.secondary"
                  variant="body2"
                  sx={{ p: 2, textAlign: 'center' }}
                >
                  Select a project first to list its experiments.
                </Typography>
              ) : loading ? (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    py: 4,
                  }}
                >
                  <CircularProgress size={20} sx={{ mr: 1 }} />
                  <Typography color="text.secondary">
                    Loading experiments...
                  </Typography>
                </Box>
              ) : loadError ? (
                <Alert severity="error">{loadError}</Alert>
              ) : filteredExperiments.length === 0 ? (
                <Typography
                  color="text.secondary"
                  variant="body2"
                  sx={{ p: 2, textAlign: 'center' }}
                >
                  {experiments.length === 0
                    ? 'No experiments with saved versions in this project.'
                    : 'No experiments match your search.'}
                </Typography>
              ) : (
                <Stack spacing={1}>
                  {filteredExperiments.map(exp => {
                    const expId = String(exp.id);
                    const versionCount = getSelectedVersionCount(expId);
                    const selected = versionCount > 0;
                    const focused = focusedId === expId;
                    return (
                      <Paper
                        key={expId}
                        elevation={0}
                        onClick={() => setFocusedId(expId)}
                        sx={{
                          p: 1.5,
                          cursor: 'pointer',
                          border: '1px solid',
                          borderColor: focused ? 'primary.main' : 'divider',
                          backgroundColor: focused
                            ? 'action.selected'
                            : 'background.paper',
                          transition: 'all 0.15s',
                          '&:hover': {
                            borderColor: 'primary.main',
                            backgroundColor: focused
                              ? 'action.selected'
                              : 'action.hover',
                          },
                        }}
                      >
                        <Stack
                          direction="row"
                          spacing={1}
                          alignItems="flex-start"
                        >
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 600,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {exp.name}
                            </Typography>
                            <Stack
                              direction="row"
                              spacing={0.5}
                              sx={{ mt: 0.5, flexWrap: 'wrap', rowGap: 0.5 }}
                            >
                              {exp.latest_version && (
                                <Chip
                                  size="small"
                                  variant="outlined"
                                  label={shortVersion(exp.latest_version)}
                                />
                              )}
                              <Chip
                                size="small"
                                variant="outlined"
                                color={
                                  exp.visibility === 'shared'
                                    ? 'primary'
                                    : 'default'
                                }
                                label={exp.visibility}
                              />
                              {selected && (
                                <Chip
                                  size="small"
                                  variant="outlined"
                                  color="primary"
                                  label={`${versionCount} ver.`}
                                />
                              )}
                            </Stack>
                          </Box>
                        </Stack>
                      </Paper>
                    );
                  })}
                </Stack>
              )}
            </Box>
          </Box>

          <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {renderDetailPane()}
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ flexDirection: 'column', alignItems: 'stretch' }}>
        {selectedRows.length > 0 && (
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 0.75,
              mb: 1,
              alignItems: 'center',
            }}
          >
            <Typography variant="caption" color="text.secondary">
              {selectedRows.length} selected — will trigger{' '}
              {selectedRows.length} run
              {selectedRows.length === 1 ? '' : 's'} per test set
            </Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleConfirm}
            disabled={editMode && savingVersion}
          >
            {selectedRows.length === 0
              ? 'Run without experiment'
              : `Use ${selectedRows.length} version${
                  selectedRows.length === 1 ? '' : 's'
                }`}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
