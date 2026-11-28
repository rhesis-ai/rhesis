'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';
import { getMetricTargetIcon } from '@/utils/metric-targets';

interface TargetChoiceRadiosProps {
  /** Id of the visible label naming the group. */
  labelledBy: string;
  choices: MetricTargetChoice[];
  /** The full registry, for each choice's icon. */
  registry: MetricTargetChoice[];
  value: string;
  onChange: (on: string) => void;
}

/** Keys that move the selection, and where to: the ARIA radio group pattern. */
const STEP_KEYS: Record<string, number> = {
  ArrowRight: 1,
  ArrowDown: 1,
  ArrowLeft: -1,
  ArrowUp: -1,
};

/**
 * The targets as one radio group: Tab reaches only the selected chip (or the
 * first, when none is), and the arrow keys, Home and End move the selection,
 * as native radio buttons do.
 */
export default function TargetChoiceRadios({
  labelledBy,
  choices,
  registry,
  value,
  onChange,
}: TargetChoiceRadiosProps) {
  const chips = React.useRef<(HTMLDivElement | null)[]>([]);
  const selectedIndex = choices.findIndex(c => c.on === value);
  const tabStop = selectedIndex >= 0 ? selectedIndex : 0;

  const move = (index: number) => {
    const next = (index + choices.length) % choices.length;
    onChange(choices[next].on);
    chips.current[next]?.focus();
  };

  const handleKeyDown = (index: number) => (event: React.KeyboardEvent) => {
    if (event.key in STEP_KEYS) {
      event.preventDefault();
      move(index + STEP_KEYS[event.key]);
    } else if (event.key === 'Home') {
      event.preventDefault();
      move(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      move(choices.length - 1);
    }
  };

  return (
    <Box
      role="radiogroup"
      aria-labelledby={labelledBy}
      sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}
    >
      {choices.map((choice, index) => {
        const isSelected = choice.on === value;
        return (
          <Tooltip key={choice.on} title={choice.description} describeChild>
            <Chip
              ref={(chip: HTMLDivElement | null) => {
                chips.current[index] = chip;
              }}
              role="radio"
              aria-checked={isSelected}
              tabIndex={index === tabStop ? 0 : -1}
              icon={getMetricTargetIcon(choice.on, registry)}
              label={choice.label}
              clickable
              color={isSelected ? 'primary' : 'default'}
              variant={isSelected ? 'filled' : 'outlined'}
              onClick={() => onChange(choice.on)}
              onKeyDown={handleKeyDown(index)}
            />
          </Tooltip>
        );
      })}
    </Box>
  );
}
