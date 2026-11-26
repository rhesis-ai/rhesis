'use client';

import React from 'react';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { drawerOutlineButtonSx } from '@/components/common/drawerFormFieldSx';
import { BiotechIcon } from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  shortVersion,
  type ExperimentDetail,
} from '@/utils/api-client/interfaces/parameters';
import type { SelectedExperiment } from '@/utils/test-run-batch';

const GROUP_BOX_SX = {
  p: 1.5,
  border: 1,
  borderColor: 'divider',
  borderRadius: BORDER_RADIUS.sm,
} as const;

export const EXPERIMENTS_HELP =
  "Each selected experiment triggers its own test run with that experiment's parameters pinned. Leave empty to run without an experiment.";

/** Experiments picked for this run, grouped by experiment, plus an "Add" button. */
export function ExperimentPicker({
  selected,
  onChange,
  onAdd,
}: {
  selected: SelectedExperiment[];
  onChange: (next: SelectedExperiment[]) => void;
  onAdd: () => void;
}) {
  const grouped = new Map<
    string,
    { name: string; versions: SelectedExperiment[] }
  >();
  for (const exp of selected) {
    const key = String(exp.experiment_id);
    const group = grouped.get(key) ?? {
      name: exp.experiment_name,
      versions: [],
    };
    group.versions.push(exp);
    grouped.set(key, group);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        {EXPERIMENTS_HELP}
      </Typography>
      {grouped.size > 0 && (
        <Stack spacing={1}>
          {Array.from(grouped.entries()).map(([expId, group]) => (
            <Box key={expId} sx={GROUP_BOX_SX}>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <BiotechIcon fontSize="small" color="primary" />
                <Typography variant="body2" noWrap>
                  {group.name}
                </Typography>
              </Box>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {group.versions.map(exp => (
                  <Chip
                    key={exp.version}
                    label={shortVersion(exp.version)}
                    size="small"
                    variant="outlined"
                    sx={{ fontFamily: 'monospace' }}
                    onDelete={() =>
                      onChange(
                        selected.filter(
                          row =>
                            row.experiment_id !== exp.experiment_id ||
                            row.version !== exp.version
                        )
                      )
                    }
                  />
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}
      <Button
        variant="outlined"
        fullWidth
        startIcon={<AddIcon />}
        onClick={onAdd}
        sx={drawerOutlineButtonSx}
      >
        Add experiment
      </Button>
    </Box>
  );
}

/** Version chips for the experiment being run (Run Experiment mode). */
export function ExperimentVersionPicker({
  experiment,
  selected,
  onToggle,
}: {
  experiment: ExperimentDetail;
  selected: Set<string>;
  onToggle: (version: string) => void;
}) {
  const seen = new Set<string>();
  const versions = experiment.versions.filter(v => {
    if (seen.has(v.version)) return false;
    seen.add(v.version);
    return true;
  });

  return (
    <Box sx={GROUP_BOX_SX}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <BiotechIcon fontSize="small" color="primary" />
        <Typography variant="body2" fontWeight="fontWeightMedium" noWrap>
          {experiment.name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          — select versions to run
        </Typography>
      </Box>
      {versions.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No versions saved yet.
        </Typography>
      ) : (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {[...versions].reverse().map(v => {
            const isSelected = selected.has(v.version);
            return (
              <Chip
                key={v.version}
                label={shortVersion(v.version)}
                size="small"
                variant={isSelected ? 'filled' : 'outlined'}
                color={isSelected ? 'primary' : 'default'}
                sx={{ fontFamily: 'monospace', cursor: 'pointer' }}
                onClick={() => onToggle(v.version)}
              />
            );
          })}
        </Stack>
      )}
    </Box>
  );
}
