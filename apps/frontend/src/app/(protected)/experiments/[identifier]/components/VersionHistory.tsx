'use client';

import * as React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Checkbox,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import RemoveIcon from '@mui/icons-material/Remove';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {
  ExperimentVersion,
  ParameterSchema,
  ParameterValue,
  ProjectEnvironments,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { PromoteIcon } from '@/components/icons';
import { renderValuePreview } from './TypedValueEditor';

interface VersionHistoryProps {
  versions: ExperimentVersion[];
  schema: ParameterSchema;
  projectEnvironments: ProjectEnvironments | null;
  experimentId: string;
  canPromote: boolean;
  onPromoteVersion: (version: string) => void;
  openVersion?: string | null;
  outcomes?: Record<string, VersionOutcomeSummary>;
  selectable?: boolean;
  selectedVersionHashes?: Set<string>;
  onSelectionChange?: (versions: Set<string>) => void;
}

export interface VersionOutcomeSummary {
  runCount: number;
  passRate: number | null;
  delta: number | null;
}

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

/**
 * Version history list with per-row Promote action and a typed
 * before/after diff vs the previous version.
 *
 * The diff is intentionally typed (renders ``temperature: 0.7 →
 * 1.4``, not ``"temperature": 0.7 → "temperature": 1.4``) so the
 * regression-finder use case ("which slot moved when pass-rate
 * dropped?") stays one glance away.
 */
export default function VersionHistory({
  versions,
  schema: _schema,
  projectEnvironments,
  experimentId,
  canPromote,
  onPromoteVersion,
  openVersion,
  outcomes = {},
  selectable = false,
  selectedVersionHashes,
  onSelectionChange,
}: VersionHistoryProps) {
  const theme = useTheme();
  const [expandedVersions, setExpandedVersions] = React.useState<Set<string>>(
    () => (openVersion ? new Set([openVersion]) : new Set())
  );

  React.useEffect(() => {
    if (!openVersion) return;
    setExpandedVersions(prev => new Set(prev).add(openVersion));
  }, [openVersion]);

  const environmentsByVersion = React.useMemo(() => {
    const map = new Map<string, string[]>();
    if (!projectEnvironments) return map;
    for (const [name, ptr] of Object.entries(
      projectEnvironments.environments
    )) {
      if (ptr === null || ptr.experiment_id !== experimentId) continue;
      const arr = map.get(ptr.version) ?? [];
      arr.push(name);
      map.set(ptr.version, arr);
    }
    return map;
  }, [projectEnvironments, experimentId]);

  if (versions.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
        <Typography variant="body2">
          No versions yet. Save values from the Edit tab to mint the first
          immutable version.
        </Typography>
      </Box>
    );
  }

  const allSelected =
    selectable &&
    selectedVersionHashes !== undefined &&
    versions.length > 0 &&
    versions.every(v => selectedVersionHashes.has(v.version));

  const someSelected =
    selectable &&
    selectedVersionHashes !== undefined &&
    !allSelected &&
    versions.some(v => selectedVersionHashes.has(v.version));

  const handleToggleAll = () => {
    if (!onSelectionChange) return;
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(versions.map(v => v.version)));
    }
  };

  const handleToggleVersion = (versionHash: string) => {
    if (!onSelectionChange || !selectedVersionHashes) return;
    const next = new Set(selectedVersionHashes);
    if (next.has(versionHash)) {
      next.delete(versionHash);
    } else {
      next.add(versionHash);
    }
    onSelectionChange(next);
  };

  // Render newest first so the most relevant entry sits at the top.
  const ordered = [...versions].reverse();

  return (
    <Stack spacing={1}>
      {selectable && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            px: 1,
            py: 0.5,
          }}
        >
          <Checkbox
            size="small"
            checked={allSelected}
            indeterminate={someSelected}
            onChange={handleToggleAll}
          />
          <Typography variant="body2" color="text.secondary">
            {allSelected ? 'Deselect all' : 'Select all'}
          </Typography>
        </Box>
      )}
      {ordered.map((version, idxFromTop) => {
        const idxFromBottom = versions.length - 1 - idxFromTop;
        const previous =
          idxFromBottom > 0 ? versions[idxFromBottom - 1] : undefined;
        const diff = diffVersions(previous, version);
        const envNames = environmentsByVersion.get(version.version) ?? [];
        const outcome = outcomes[version.version];
        const delta = outcome?.delta ?? null;
        const isImproved = delta !== null && delta > 0;
        const isRegressed = delta !== null && delta < 0;
        const isUnchanged = delta !== null && delta === 0;
        const deltaColor = isImproved
          ? theme.palette.success.main
          : isRegressed
            ? theme.palette.error.main
            : theme.palette.text.secondary;
        const DeltaIcon = isImproved
          ? TrendingUpIcon
          : isRegressed
            ? TrendingDownIcon
            : RemoveIcon;
        const isHighlighted = version.version === openVersion;

        return (
          <Accordion
            key={version.version}
            expanded={expandedVersions.has(version.version)}
            sx={{
              border: '1px solid',
              borderColor: isHighlighted ? 'primary.main' : 'divider',
              bgcolor: isHighlighted ? 'action.selected' : 'background.paper',
              '&:before': {
                display: 'none',
              },
            }}
            onChange={(_, expanded) => {
              setExpandedVersions(prev => {
                const next = new Set(prev);
                if (expanded) {
                  next.add(version.version);
                } else {
                  next.delete(version.version);
                }
                return next;
              });
            }}
          >
            <AccordionSummary>
              <Stack
                direction="row"
                spacing={2}
                alignItems="center"
                sx={{ width: '100%', mr: 2 }}
              >
                {selectable && (
                  <Checkbox
                    size="small"
                    checked={
                      selectedVersionHashes?.has(version.version) ?? false
                    }
                    onClick={e => e.stopPropagation()}
                    onChange={() => handleToggleVersion(version.version)}
                  />
                )}
                <Chip
                  size="small"
                  label={shortVersion(version.version)}
                  color={isHighlighted ? 'primary' : 'default'}
                  variant={isHighlighted ? 'filled' : 'outlined'}
                  sx={{ fontFamily: 'monospace' }}
                />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2">
                    {version.message || (
                      <Box component="em" sx={{ color: 'text.disabled' }}>
                        (no message)
                      </Box>
                    )}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(version.created_at).toLocaleString()}
                  </Typography>
                </Box>
                {envNames.map(name => (
                  <Chip key={name} size="small" color="success" label={name} />
                ))}
                {outcome && (
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      flexWrap: 'wrap',
                    }}
                  >
                    <Typography variant="body2" color="text.secondary">
                      {outcome.runCount} run
                      {outcome.runCount === 1 ? '' : 's'}
                      {' • '}Pass rate:
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>
                      {outcome.passRate !== null
                        ? `${outcome.passRate.toFixed(1)}%`
                        : 'N/A'}
                    </Typography>
                    {delta !== null && (
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.25,
                        }}
                      >
                        <DeltaIcon
                          fontSize="small"
                          sx={{ color: deltaColor }}
                        />
                        <Typography
                          variant="caption"
                          sx={{ color: deltaColor, fontWeight: 500 }}
                        >
                          {isUnchanged
                            ? '0.0%'
                            : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                )}
                <Tooltip
                  title={
                    canPromote
                      ? 'Promote this version onto a project environment'
                      : 'Share the experiment first to promote'
                  }
                >
                  <span>
                    <Button
                      component="span"
                      size="small"
                      startIcon={<PromoteIcon />}
                      disabled={!canPromote}
                      onClick={e => {
                        e.stopPropagation();
                        onPromoteVersion(version.version);
                      }}
                    >
                      Promote
                    </Button>
                  </span>
                </Tooltip>
              </Stack>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="overline" color="text.secondary">
                    Values
                  </Typography>
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
                </Box>
                {previous && diff.length > 0 && (
                  <Box>
                    <Typography variant="overline" color="text.secondary">
                      Diff vs {shortVersion(previous.version)}
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
                                  textDecoration: entry.after
                                    ? 'line-through'
                                    : 'none',
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
                )}
                {previous && diff.length === 0 && (
                  <Typography variant="caption" color="text.secondary">
                    Only metadata changed (message / parent pointer); no slot
                    values differ from {shortVersion(previous.version)}.
                  </Typography>
                )}
              </Stack>
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Stack>
  );
}
