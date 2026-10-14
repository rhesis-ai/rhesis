'use client';

import * as React from 'react';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import { alpha, type Theme } from '@mui/material/styles';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { actionArea, actionLabel } from '../labels';
import { AuditActorType, AuditOutcome } from '../types';
import { monoSx } from './AuditChanges';

export type Tone = 'primary' | 'success' | 'warning' | 'info' | 'error';

/** A tinted fill with readable text, in either mode. */
export function toneSx(tone: Tone) {
  return {
    bgcolor: (t: Theme) =>
      alpha(t.palette[tone].main, t.palette.action.focusOpacity),
    color: (t: Theme) =>
      t.palette.mode === 'light' ? t.palette[tone].dark : t.palette[tone].main,
  };
}

/** One colour per role editor area, so a glance tells the kind of change. */
const AREA_TONES: Record<string, Tone> = {
  'test-resources': 'success',
  observability: 'info',
  infrastructure: 'warning',
  administration: 'primary',
};

export function actionTone(action: string, outcome: string): Tone {
  if (outcome !== AuditOutcome.SUCCESS) return 'error';
  const area = actionArea(action);
  return (area && AREA_TONES[area.id]) ?? 'primary';
}

const pillSx = {
  display: 'inline-block',
  px: 1,
  py: 0.25,
  borderRadius: BORDER_RADIUS.xs,
  whiteSpace: 'nowrap',
  maxWidth: '100%',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  verticalAlign: 'middle',
} as const;

/** The action id, coloured by area, red when denied or failed. */
export function ActionChip({
  action,
  outcome,
}: {
  action: string;
  outcome: string;
}) {
  return (
    <Tooltip title={actionLabel(action, outcome)}>
      <Box
        component="span"
        sx={{
          ...pillSx,
          ...monoSx,
          wordBreak: 'normal',
          typography: 'caption',
          ...toneSx(actionTone(action, outcome)),
        }}
      >
        {action}
      </Box>
    </Tooltip>
  );
}

/** A small rounded status label, e.g. a destination's state. */
export function StatusPill({
  tone,
  children,
}: {
  tone: Tone | 'default';
  children: React.ReactNode;
}) {
  return (
    <Box
      component="span"
      sx={{
        ...pillSx,
        px: 1.25,
        borderRadius: BORDER_RADIUS.pill,
        typography: 'caption',
        ...(tone === 'default'
          ? {
              bgcolor: (t: Theme) => t.palette.greyscale.surface2,
              color: 'text.secondary',
            }
          : toneSx(tone)),
      }}
    >
      {children}
    </Box>
  );
}

/** An outlined tag, used for the event source. */
export function OutlinedTag({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="span"
      sx={{
        ...pillSx,
        typography: 'captionBold',
        color: 'text.secondary',
        border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
      }}
    >
      {children}
    </Box>
  );
}

const AVATAR_TONES: readonly Tone[] = ['primary', 'success', 'warning', 'info'];

function initials(name: string): string {
  const words = name.split(/[\s@._-]+/).filter(Boolean);
  const letters = words.length > 1 ? words[0][0] + words[1][0] : name[0];
  return (letters ?? '?').toUpperCase();
}

function nameTone(name: string): Tone {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_TONES[hash % AVATAR_TONES.length];
}

const API_ACTORS: readonly string[] = [
  AuditActorType.API_TOKEN,
  AuditActorType.API_CLIENT,
];
const API_INITIALS = 'API';
const UNKNOWN_INITIALS = '?';

/** Initials for people, a dark tile for API credentials, red for unknown callers. */
export function ActorAvatar({
  name,
  actorType,
}: {
  name: string;
  actorType: string;
}) {
  const base = {
    width: AVATAR_SIZES.SMALL,
    height: AVATAR_SIZES.SMALL,
    typography: 'captionBold',
    flexShrink: 0,
  };
  if (API_ACTORS.includes(actorType)) {
    return (
      <Avatar
        variant="rounded"
        sx={{
          ...base,
          bgcolor: (t: Theme) => t.palette.greyscale.title,
          color: (t: Theme) => t.palette.background.paper,
        }}
      >
        {API_INITIALS}
      </Avatar>
    );
  }
  if (actorType === AuditActorType.ANONYMOUS) {
    return (
      <Avatar sx={{ ...base, ...toneSx('error') }}>{UNKNOWN_INITIALS}</Avatar>
    );
  }
  return (
    <Avatar sx={{ ...base, ...toneSx(nameTone(name)) }}>
      {initials(name)}
    </Avatar>
  );
}
