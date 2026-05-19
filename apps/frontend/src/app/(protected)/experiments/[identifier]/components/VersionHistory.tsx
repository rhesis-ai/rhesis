'use client';

import * as React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
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
} from '@mui/material';
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
}: VersionHistoryProps) {
  const environmentsByVersion = React.useMemo(() => {
    const map = new Map<string, string[]>();
    if (!projectEnvironments) return map;
    for (const [name, ptr] of Object.entries(projectEnvironments.environments)) {
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
          No versions yet. Save values from the Edit tab to mint the
          first immutable version.
        </Typography>
      </Box>
    );
  }

  // Render newest first so the most relevant entry sits at the top.
  const ordered = [...versions].reverse();

  return (
    <Stack spacing={1}>
      {ordered.map((version, idxFromTop) => {
        const idxFromBottom = versions.length - 1 - idxFromTop;
        const previous = idxFromBottom > 0 ? versions[idxFromBottom - 1] : undefined;
        const diff = diffVersions(previous, version);
        const envNames = environmentsByVersion.get(version.version) ?? [];

        return (
          <Accordion key={version.version} defaultExpanded={idxFromTop === 0}>
            <AccordionSummary>
              <Stack
                direction="row"
                spacing={2}
                alignItems="center"
                sx={{ width: '100%', mr: 2 }}
              >
                <Chip
                  size="small"
                  label={shortVersion(version.version)}
                  sx={{ fontFamily: 'monospace' }}
                />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2">
                    {version.message || (
                      <Box
                        component="em"
                        sx={{ color: 'text.disabled' }}
                      >
                        (no message)
                      </Box>
                    )}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(version.created_at).toLocaleString()}
                  </Typography>
                </Box>
                {envNames.map(name => (
                  <Chip
                    key={name}
                    size="small"
                    color="success"
                    label={name}
                  />
                ))}
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
                  <Typography
                    variant="overline"
                    color="text.secondary"
                  >
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
                    <Typography
                      variant="overline"
                      color="text.secondary"
                    >
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
                    Only metadata changed (message / parent pointer);
                    no slot values differ from{' '}
                    {shortVersion(previous.version)}.
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
