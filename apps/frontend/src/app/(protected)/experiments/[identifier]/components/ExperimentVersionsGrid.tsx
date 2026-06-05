'use client';

import * as React from 'react';
import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowParams,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import BaseDrawer from '@/components/common/BaseDrawer';
import GridToolbar from '@/components/common/GridToolbar';
import SectionCard from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';
import { PlayArrowIcon, PromoteIcon, SaveIcon } from '@/components/icons';
import {
  ExperimentDetail,
  ExperimentVersion,
  ParameterSchema,
  ParameterValue,
  ProjectEnvironments,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { renderValuePreview } from './TypedValueEditor';

interface DiffEntry {
  name: string;
  before: ParameterValue | null;
  after: ParameterValue | null;
}

function diffVersions(
  prev: ExperimentVersion | undefined,
  curr: ExperimentVersion
): DiffEntry[] {
  const out: DiffEntry[] = [];
  const prevValues = prev ? prev.values : {};
  const allKeys = new Set([
    ...Object.keys(prevValues),
    ...Object.keys(curr.values),
  ]);
  for (const name of allKeys) {
    const before = (prevValues[name] as ParameterValue | undefined) ?? null;
    const after = (curr.values[name] as ParameterValue | undefined) ?? null;
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      out.push({ name, before, after });
    }
  }
  return out;
}

interface ExperimentVersionsGridProps {
  experiment: ExperimentDetail;
  schema: ParameterSchema;
  projectEnvironments: ProjectEnvironments | null;
  canPromote: boolean;
  onPromoteVersion: (version: string) => void;
  /** Called when user clicks "Run this version" — pre-seeds the RunDrawer with this version hash */
  onRunVersion: (versionHash: string) => void;
  /** Opens the "Add configuration" drawer in the parent */
  onAddConfiguration?: () => void;
}

export default function ExperimentVersionsGrid({
  experiment,
  schema,
  projectEnvironments,
  canPromote,
  onPromoteVersion,
  onRunVersion,
  onAddConfiguration,
}: ExperimentVersionsGridProps) {
  const [drawerVersion, setDrawerVersion] = useState<ExperimentVersion | null>(
    null
  );
  const [searchQuery, setSearchQuery] = useState('');

  const environmentsByVersion = useMemo(() => {
    const map = new Map<string, string[]>();
    if (!projectEnvironments) return map;
    for (const [name, ptr] of Object.entries(
      projectEnvironments.environments
    )) {
      if (ptr === null || ptr.experiment_id !== experiment.id) continue;
      const arr = map.get(ptr.version) ?? [];
      arr.push(name);
      map.set(ptr.version, arr);
    }
    return map;
  }, [projectEnvironments, experiment.id]);

  const uniqueVersions = useMemo(() => {
    const seen = new Set<string>();
    return experiment.versions.filter(v => {
      if (seen.has(v.version)) return false;
      seen.add(v.version);
      return true;
    });
  }, [experiment.versions]);

  const orderedVersions = useMemo(
    () => [...uniqueVersions].reverse(),
    [uniqueVersions]
  );

  const filteredVersions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return orderedVersions;
    return orderedVersions.filter(
      v =>
        v.version.toLowerCase().includes(q) ||
        (v.message ?? '').toLowerCase().includes(q)
    );
  }, [orderedVersions, searchQuery]);

  const drawerPreviousVersion = useMemo(() => {
    if (!drawerVersion) return undefined;
    const idx = uniqueVersions.findIndex(
      v => v.version === drawerVersion.version
    );
    return idx > 0 ? uniqueVersions[idx - 1] : undefined;
  }, [drawerVersion, uniqueVersions]);

  const drawerDiff = useMemo(
    () =>
      drawerVersion ? diffVersions(drawerPreviousVersion, drawerVersion) : [],
    [drawerPreviousVersion, drawerVersion]
  );

  const columns: GridColDef<ExperimentVersion>[] = useMemo(
    () => [
      {
        field: 'version',
        headerName: 'Version',
        flex: 0.8,
        renderCell: (params: GridRenderCellParams<ExperimentVersion>) => (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              height: '100%',
              gap: 0.25,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {shortVersion(params.row.version)}
              </Typography>
              {environmentsByVersion.get(params.row.version)?.map(env => (
                <Chip key={env} size="small" color="success" label={env} />
              ))}
            </Box>
            {params.row.message && (
              <Typography variant="caption" color="text.secondary" noWrap>
                {params.row.message}
              </Typography>
            )}
          </Box>
        ),
      },
      ...schema.fields.map(field => ({
        field: `values.${field.name}`,
        headerName: field.name,
        flex: 1,
        sortable: false,
        valueGetter: (_: unknown, row: ExperimentVersion) =>
          row.values[field.name] ?? null,
        renderCell: (params: GridRenderCellParams<ExperimentVersion>) => {
          const val = params.row.values[field.name] as
            | ParameterValue
            | undefined;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              {val !== undefined ? (
                <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                  {renderValuePreview(val)}
                </Typography>
              ) : (
                <Typography
                  variant="body2"
                  color="text.disabled"
                  fontStyle="italic"
                >
                  —
                </Typography>
              )}
            </Box>
          );
        },
      })),
      {
        field: 'created_at',
        headerName: 'Saved at',
        flex: 0.9,
        renderCell: (params: GridRenderCellParams<ExperimentVersion>) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" color="text.secondary">
              {new Date(params.row.created_at).toLocaleString()}
            </Typography>
          </Box>
        ),
      },
    ],
    [environmentsByVersion, schema.fields]
  );

  const cardActions = onAddConfiguration && (
    <Button
      variant="outlined"
      startIcon={<SaveIcon />}
      onClick={onAddConfiguration}
      disabled={schema.fields.length === 0}
      size="small"
    >
      Add configuration
    </Button>
  );

  return (
    <>
      <SectionCard
        title={`Versions (${orderedVersions.length})`}
        actions={cardActions ?? undefined}
      >
        <GridToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search versions…"
          sx={{ px: 0, pt: 0, pb: '24px' }}
        />
        {orderedVersions.length === 0 ? (
          <Alert severity="info">
            No versions yet. Use &quot;Add configuration&quot; to define values
            and save the first immutable version.
          </Alert>
        ) : filteredVersions.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ py: 4, textAlign: 'center' }}
          >
            No versions match your search.
          </Typography>
        ) : (
          <BaseDataGrid
            rows={filteredVersions}
            columns={columns}
            getRowId={row => row.version}
            onRowClick={(params: GridRowParams<ExperimentVersion>) =>
              setDrawerVersion(params.row)
            }
            disablePaperWrapper
            hideFooter={filteredVersions.length <= 25}
            sx={{ cursor: 'pointer' }}
          />
        )}
      </SectionCard>

      <BaseDrawer
        open={!!drawerVersion}
        onClose={() => setDrawerVersion(null)}
        title={
          drawerVersion ? `Version ${shortVersion(drawerVersion.version)}` : ''
        }
        showHeader
        width={600}
        saveButtonText=""
        closeButtonText="Close"
      >
        {drawerVersion && (
          <DrawerContent
            version={drawerVersion}
            previousVersion={drawerPreviousVersion}
            diff={drawerDiff}
            envNames={environmentsByVersion.get(drawerVersion.version) ?? []}
            canPromote={canPromote}
            onPromote={() => {
              onPromoteVersion(drawerVersion.version);
              setDrawerVersion(null);
            }}
            onRunVersion={() => {
              onRunVersion(drawerVersion.version);
              setDrawerVersion(null);
            }}
          />
        )}
      </BaseDrawer>
    </>
  );
}

function DrawerContent({
  version,
  previousVersion,
  diff,
  envNames,
  canPromote,
  onPromote,
  onRunVersion,
}: {
  version: ExperimentVersion;
  previousVersion: ExperimentVersion | undefined;
  diff: DiffEntry[];
  envNames: string[];
  canPromote: boolean;
  onPromote: () => void;
  onRunVersion: () => void;
}) {
  return (
    <Stack spacing={3}>
      <Stack spacing={2}>
        <ViewField label="Version" value={shortVersion(version.version)} />
        <ViewField
          label="Saved at"
          value={new Date(version.created_at).toLocaleString()}
        />
        {version.message && (
          <ViewField label="Message" value={version.message} />
        )}
        {envNames.length > 0 && (
          <Box>
            <Typography
              sx={{
                fontSize: 14,
                color: 'text.secondary',
                px: '14px',
                mb: '6px',
              }}
            >
              Active Environments
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, px: '14px' }}>
              {envNames.map(name => (
                <Chip key={name} size="small" color="success" label={name} />
              ))}
            </Box>
          </Box>
        )}
      </Stack>

      <Divider />

      <Box>
        <Typography variant="overline" color="text.secondary">
          Values
        </Typography>
        {Object.keys(version.values).length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No values recorded for this version.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableBody>
                {Object.entries(version.values).map(([name, val]) => (
                  <TableRow key={name}>
                    <TableCell
                      sx={{
                        fontFamily: 'monospace',
                        color: 'text.secondary',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {name}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>
                      {renderValuePreview(val as ParameterValue)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      {previousVersion && diff.length > 0 && (
        <>
          <Divider />
          <Box>
            <Typography variant="overline" color="text.secondary">
              Diff vs {shortVersion(previousVersion.version)}
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Slot</TableCell>
                    <TableCell>Before</TableCell>
                    <TableCell>After</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {diff.map(entry => (
                    <TableRow key={entry.name}>
                      <TableCell sx={{ fontFamily: 'monospace' }}>
                        {entry.name}
                      </TableCell>
                      <TableCell
                        sx={{
                          fontFamily: 'monospace',
                          color: 'text.secondary',
                          textDecoration: entry.after ? 'line-through' : 'none',
                        }}
                      >
                        {renderValuePreview(entry.before)}
                      </TableCell>
                      <TableCell sx={{ fontFamily: 'monospace' }}>
                        {renderValuePreview(entry.after)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </>
      )}

      {previousVersion && diff.length === 0 && (
        <Typography variant="caption" color="text.secondary">
          No slot values changed from {shortVersion(previousVersion.version)}.
        </Typography>
      )}

      <Divider />

      <Button
        variant="contained"
        startIcon={<PlayArrowIcon />}
        onClick={onRunVersion}
        fullWidth
      >
        Run this version
      </Button>

      <Tooltip
        title={
          canPromote
            ? 'Promote this version to a project environment'
            : 'Share the experiment first to promote'
        }
      >
        <span>
          <Button
            variant="outlined"
            startIcon={<PromoteIcon />}
            disabled={!canPromote}
            onClick={onPromote}
            fullWidth
          >
            Promote to environment
          </Button>
        </span>
      </Tooltip>
    </Stack>
  );
}
