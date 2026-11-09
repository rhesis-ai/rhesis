'use client';

import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import { alpha, useTheme, type Theme } from '@mui/material/styles';
import {
  Box,
  ButtonBase,
  Typography,
  Avatar,
  IconButton,
  Tooltip,
} from '@mui/material';
import { DeleteIcon } from '@/components/icons';
import { BORDER_RADIUS, ELEVATION, GRID_CARD_INSET } from '@/styles/theme';
import GridBadge from '@/components/common/GridBadge';

export type EntityCardTone = 'neutral' | 'success' | 'warning' | 'error';

/**
 * One fact in the line under the title. `type` is what kind of thing this is
 * (one blue chip), `state` a status or weight (a coloured dot and a word), and
 * `plain` anything else (muted text, joined by "·").
 */
export type EntityCardFact =
  | { key: string; kind: 'type'; label: string }
  | {
      key: string;
      kind: 'state';
      label: string;
      tone?: EntityCardTone;
      /** Dot colour as a palette path (e.g. 'info.main'); wins over `tone`. */
      color?: string;
    }
  | { key: string; kind: 'plain'; label: string; mono?: boolean };

/**
 * A linked thing below the divider. With `count`, renders "**7** metrics" and
 * greys out at zero; without, renders `label` as one line (e.g. a list of names).
 */
export interface EntityCardRelation {
  key: string;
  label: string;
  count?: number;
  /** With a count, shown instead of the label, which moves to a tooltip. */
  icon?: React.ReactNode;
  /** Greys the entry out. Defaults to true when `count` is 0. */
  muted?: boolean;
}

export interface EntityCardProps {
  icon?: React.ReactNode;
  title: string;
  description?: string | null;
  onClick?: () => void;
  onDelete?: () => void;
  /** When set, the delete button renders disabled with this as its tooltip. */
  deleteDisabledReason?: string;
  /** Accessible name for the delete button, and its tooltip when enabled. */
  deleteLabel?: string;
  /** Where it lives: a parent, a provider, a repository. One muted line. */
  context?: React.ReactNode;
  /** At most three; see {@link EntityCardFact}. */
  facts?: EntityCardFact[];
  relations?: EntityCardRelation[];
  userAvatar?: string;
  userName?: string;
  /** ISO timestamp, shown as "Updated 3 days ago" in the footer. */
  updatedAt?: string | null;
  /** Right side of the footer, e.g. a "Request access" button. */
  footerAction?: React.ReactNode;
  topRightActions?: React.ReactNode;
  /** Overrides the default card border color (e.g. 'warning.main' for validation errors) */
  borderColor?: string;
  /** Lines the description is clamped to and always reserves. */
  descriptionLines?: number;
}

const DESCRIPTION_LINE_HEIGHT = 22;
const DESCRIPTION_MAX_LINES = 2;
/** Line heights the optional slots reserve, so cards in a grid row line up. */
const CONTEXT_LINE_HEIGHT = 20;
const FACTS_LINE_HEIGHT = 24;
const RELATIONS_LINE_HEIGHT = 22;

function toneColor(tone: EntityCardTone, theme: Theme): string {
  switch (tone) {
    case 'success':
      return theme.palette.success.main;
    case 'warning':
      return theme.palette.warning.main;
    case 'error':
      return theme.palette.error.main;
    default:
      return theme.palette.text.disabled;
  }
}

const smallMutedSx = {
  fontSize: 13,
  lineHeight: '20px',
  color: 'text.secondary',
  whiteSpace: 'nowrap',
} as const;

function Fact({ fact }: { fact: EntityCardFact }) {
  const theme = useTheme();
  if (fact.kind === 'type') {
    return (
      <GridBadge
        label={fact.label}
        sx={{
          bgcolor: alpha(theme.palette.primary.main, 0.12),
          color: 'primary.main',
          fontWeight: 600,
        }}
      />
    );
  }
  if (fact.kind === 'state') {
    return (
      <Box
        component="span"
        sx={{
          ...smallMutedSx,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.75,
        }}
      >
        <Box
          component="span"
          aria-hidden
          sx={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            flexShrink: 0,
            bgcolor: fact.color ?? toneColor(fact.tone ?? 'neutral', theme),
          }}
        />
        {fact.label}
      </Box>
    );
  }
  return (
    <Box
      component="span"
      data-fact="plain"
      sx={{
        ...smallMutedSx,
        fontFamily: fact.mono ? 'monospace' : undefined,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        minWidth: 0,
      }}
    >
      {fact.label}
    </Box>
  );
}

function Relation({ relation }: { relation: EntityCardRelation }) {
  const muted = relation.muted ?? relation.count === 0;
  if (relation.count === undefined) {
    return (
      <Box
        component="span"
        sx={{ color: muted ? 'text.disabled' : 'text.primary' }}
      >
        {relation.label}
      </Box>
    );
  }
  if (relation.icon) {
    const text = `${relation.count} ${relation.label}`;
    return (
      <Tooltip title={text}>
        <Box
          component="span"
          aria-label={text}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            color: muted ? 'text.disabled' : 'text.primary',
            '& .MuiSvgIcon-root': {
              fontSize: 16,
              color: muted ? 'inherit' : 'text.secondary',
            },
          }}
        >
          {relation.icon}
          <Box component="b" sx={{ fontWeight: muted ? 400 : 600 }}>
            {relation.count}
          </Box>
        </Box>
      </Tooltip>
    );
  }
  return (
    <Box component="span" sx={{ color: muted ? 'text.disabled' : undefined }}>
      <Box
        component="b"
        sx={{
          fontWeight: muted ? 400 : 600,
          color: muted ? 'inherit' : 'text.primary',
        }}
      >
        {relation.count}
      </Box>{' '}
      {relation.label}
    </Box>
  );
}

export default function EntityCard({
  icon,
  title,
  description,
  onClick,
  onDelete,
  deleteDisabledReason,
  deleteLabel = 'Delete',
  context,
  facts = [],
  relations = [],
  userAvatar,
  userName,
  updatedAt,
  footerAction,
  topRightActions,
  borderColor: borderColorProp,
  descriptionLines = DESCRIPTION_MAX_LINES,
}: EntityCardProps) {
  const theme = useTheme();

  const firstName = userName ? userName.split(' ')[0] : undefined;
  const hasTopRightContent = !!topRightActions || !!onDelete;
  const updatedText = updatedAt
    ? `Updated ${formatDistanceToNow(new Date(updatedAt), { addSuffix: true })}`
    : null;
  const hasFooter = !!firstName || !!updatedText || !!footerAction;

  const isDark = theme.palette.mode === 'dark';
  const defaultBorderColor = isDark
    ? theme.palette.divider
    : theme.palette.greyscale.border;
  const resolvedBorderColor = borderColorProp ?? defaultBorderColor;

  // Plain facts are joined by "·"; chips and dots stand on their own.
  const factNodes: React.ReactNode[] = [];
  facts.forEach((fact, i) => {
    if (fact.kind === 'plain' && facts[i - 1]?.kind === 'plain') {
      factNodes.push(
        <Box
          component="span"
          key={`${fact.key}-sep`}
          aria-hidden
          sx={{ ...smallMutedSx, color: 'text.disabled' }}
        >
          ·
        </Box>
      );
    }
    factNodes.push(<Fact key={fact.key} fact={fact} />);
  });

  return (
    <ButtonBase
      component="div"
      data-testid="entity-card"
      onClick={onClick}
      tabIndex={onClick ? 0 : -1}
      disableRipple={!onClick}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        justifyContent: 'flex-start',
        textAlign: 'left',
        bgcolor: 'background.paper',
        border: `1px solid ${resolvedBorderColor}`,
        borderRadius: BORDER_RADIUS.md,
        p: GRID_CARD_INSET,
        boxShadow: ELEVATION.xs,
        position: 'relative',
        gap: 1.25,
        cursor: onClick ? 'pointer' : 'inherit',
        height: '100%',
        boxSizing: 'border-box',
        transition: 'box-shadow 0.2s ease',
        '&:hover': onClick
          ? { boxShadow: '0px 6px 16px rgba(0,0,0,0.14)' }
          : {},
      }}
    >
      {hasTopRightContent && (
        <Box
          sx={{
            position: 'absolute',
            top: '14px',
            right: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '2px',
            zIndex: 1,
          }}
          onClick={e => e.stopPropagation()}
        >
          {topRightActions}
          {onDelete && (
            <Tooltip title={deleteDisabledReason || deleteLabel}>
              {/* The span keeps the tooltip working on a disabled button, and
                  carries the cursor — MUI sets pointer-events: none on the
                  button itself once disabled. */}
              <Box
                component="span"
                sx={{
                  display: 'inline-flex',
                  cursor: deleteDisabledReason ? 'not-allowed' : undefined,
                }}
              >
                <IconButton
                  size="small"
                  aria-label={deleteLabel}
                  disabled={!!deleteDisabledReason}
                  onClick={e => {
                    e.stopPropagation();
                    onDelete();
                  }}
                  sx={{
                    color: 'primary.dark',
                    padding: '2px',
                    '& .MuiSvgIcon-root': { fontSize: 20 },
                  }}
                >
                  <DeleteIcon />
                </IconButton>
              </Box>
            </Tooltip>
          )}
        </Box>
      )}

      {/* 1 Context */}
      <Typography
        component="div"
        data-testid="entity-card-context"
        sx={{
          ...smallMutedSx,
          minHeight: `${CONTEXT_LINE_HEIGHT}px`,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          pr: hasTopRightContent ? '36px' : 0,
        }}
      >
        {context}
      </Typography>

      {/* 2 Title row */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: icon ? '10px' : 0,
        }}
      >
        {icon && (
          <Box
            sx={{
              width: 24,
              height: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'text.primary',
              flexShrink: 0,
              '& .MuiSvgIcon-root': { fontSize: 20 },
              '& svg:not(.MuiSvgIcon-root)': { width: 20, height: 20 },
            }}
          >
            {icon}
          </Box>
        )}
        <Typography
          sx={{
            fontSize: 18,
            fontWeight: 700,
            lineHeight: '25px',
            color: 'text.primary',
            wordBreak: 'break-word',
            flex: 1,
            pr: hasTopRightContent ? '36px' : 0,
          }}
        >
          {title}
        </Typography>
      </Box>

      {/* 3 Facts */}
      <Box
        data-testid="entity-card-facts"
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          columnGap: 1.25,
          rowGap: 0.75,
          minHeight: `${FACTS_LINE_HEIGHT}px`,
        }}
      >
        {factNodes}
      </Box>

      <Typography
        data-testid="entity-card-description"
        sx={{
          fontSize: 14,
          fontWeight: 400,
          lineHeight: `${DESCRIPTION_LINE_HEIGHT}px`,
          minHeight: `${DESCRIPTION_LINE_HEIGHT * descriptionLines}px`,
          color: 'text.primary',
          display: '-webkit-box',
          WebkitLineClamp: descriptionLines,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {description ?? ''}
      </Typography>
      <Box
        sx={{
          height: '1px',
          bgcolor: resolvedBorderColor,
          width: '100%',
          my: 0.75,
        }}
      />

      {/* 4 Relations */}
      <Box
        data-testid="entity-card-relations"
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          columnGap: 2,
          rowGap: 0.5,
          fontSize: 14,
          lineHeight: `${RELATIONS_LINE_HEIGHT}px`,
          minHeight: `${RELATIONS_LINE_HEIGHT}px`,
          color: 'text.secondary',
        }}
      >
        {relations.map(relation => (
          <Relation key={relation.key} relation={relation} />
        ))}
      </Box>

      {/* 5 Footer */}
      {hasFooter && (
        <Box
          sx={{
            ...smallMutedSx,
            mt: 'auto',
            pt: 1.25,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            {firstName && (
              <>
                <Avatar
                  src={userAvatar}
                  sx={{ width: 20, height: 20, fontSize: 11 }}
                >
                  {!userAvatar ? firstName[0].toUpperCase() : undefined}
                </Avatar>
                {firstName}
              </>
            )}
          </Box>
          {footerAction ? (
            <Box onClick={e => e.stopPropagation()}>{footerAction}</Box>
          ) : (
            updatedText
          )}
        </Box>
      )}
    </ButtonBase>
  );
}
