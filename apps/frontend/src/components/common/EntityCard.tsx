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
  Skeleton,
  Tooltip,
} from '@mui/material';
import { DeleteIcon } from '@/components/icons';
import { BORDER_RADIUS, ELEVATION, GRID_CARD_INSET } from '@/styles/theme';
import GridBadge from '@/components/common/GridBadge';
import { rem } from '@/styles/theme-constants';
import {
  SkeletonSlot,
  useSkeletonMode,
} from '@/components/loading/SkeletonMode';
import { delayedRevealSx } from '@/components/loading/DelayedReveal';

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
  /** Replaces that tooltip's "7 metrics", e.g. to list the names. */
  tooltip?: string;
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

/** Cards a loading view draws: two rows at the directories' three columns. */
const SKELETON_CARD_COUNT = 6;

/** Keys for a loading view's placeholder cards. */
export const skeletonCardKeys = Array.from(
  { length: SKELETON_CARD_COUNT },
  (_, i) => `skeleton-card-${i}`
);

/** Last description line's length in skeleton mode, so it reads as a paragraph. */
const SKELETON_LAST_LINE_WIDTH = '60%';

/**
 * A text placeholder exactly as wide as `children`: `fit-content` keeps it
 * from stretching across a block parent.
 */
function TextSlot({ children }: { children: React.ReactNode }) {
  return (
    <SkeletonSlot variant="text" sx={{ maxWidth: 'fit-content' }}>
      <span>{children}</span>
    </SkeletonSlot>
  );
}

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
  fontSize: rem(13),
  lineHeight: rem(20),
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
      <Tooltip title={relation.tooltip ?? text}>
        <Box
          component="span"
          aria-label={text}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            color: muted ? 'text.disabled' : 'text.primary',
            '& .MuiSvgIcon-root': {
              fontSize: rem(16),
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
  // In a route's loading view the card keeps its layout and draws every value
  // as a placeholder of that value's size; nothing is clickable.
  const skeleton = useSkeletonMode();
  const slot = (node: React.ReactNode) =>
    skeleton && node ? <TextSlot>{node}</TextSlot> : node;

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
          sx={{
            ...smallMutedSx,
            color: 'text.disabled',
            visibility: skeleton ? 'hidden' : undefined,
          }}
        >
          ·
        </Box>
      );
    }
    const node = <Fact key={fact.key} fact={fact} />;
    factNodes.push(
      !skeleton ? (
        node
      ) : fact.kind === 'type' ? (
        <SkeletonSlot key={fact.key}>{node}</SkeletonSlot>
      ) : (
        <TextSlot key={fact.key}>{node}</TextSlot>
      )
    );
  });

  // The card is not itself a button: it holds other buttons (delete, actions),
  // and nested controls confuse screen readers (WCAG 4.1.2). The title is the
  // keyboard control; a click anywhere else on the card bubbles to here.
  return (
    <Box
      data-testid="entity-card"
      onClick={skeleton ? undefined : onClick}
      inert={skeleton || undefined}
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
        cursor: onClick && !skeleton ? 'pointer' : 'inherit',
        height: '100%',
        boxSizing: 'border-box',
        transition: 'box-shadow 0.2s ease',
        '&:hover':
          onClick && !skeleton
            ? { boxShadow: '0px 6px 16px rgba(0,0,0,0.14)' }
            : {},
        // Inside the edge: card grids clip anything drawn outside the card.
        '&:has(.entity-card-open:focus-visible)': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: -2,
        },
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
          {skeleton && topRightActions ? (
            <SkeletonSlot>
              <Box component="span" sx={{ display: 'inline-flex' }}>
                {topRightActions}
              </Box>
            </SkeletonSlot>
          ) : (
            topRightActions
          )}
          {onDelete && (
            <SkeletonSlot variant="circular">
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
                      '& .MuiSvgIcon-root': { fontSize: rem(20) },
                    }}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Box>
              </Tooltip>
            </SkeletonSlot>
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
        {slot(context)}
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
          <SkeletonSlot variant="circular">
            <Box
              sx={{
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'text.primary',
                flexShrink: 0,
                '& .MuiSvgIcon-root': { fontSize: rem(20) },
                '& svg:not(.MuiSvgIcon-root)': { width: 20, height: 20 },
              }}
            >
              {icon}
            </Box>
          </SkeletonSlot>
        )}
        <Typography
          sx={{
            fontSize: rem(18),
            fontWeight: 700,
            lineHeight: rem(25),
            color: 'text.primary',
            wordBreak: 'break-word',
            flex: 1,
            pr: hasTopRightContent ? '36px' : 0,
          }}
        >
          {skeleton ? (
            <TextSlot>{title}</TextSlot>
          ) : onClick ? (
            <ButtonBase
              className="entity-card-open"
              disableRipple
              // The card's own onClick handles the click; this is the focus target.
              sx={{
                font: 'inherit',
                color: 'inherit',
                textAlign: 'left',
                '&:focus-visible, &.Mui-focusVisible': { outline: 'none' },
              }}
            >
              {title}
            </ButtonBase>
          ) : (
            title
          )}
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
          fontSize: rem(14),
          fontWeight: 400,
          lineHeight: `${DESCRIPTION_LINE_HEIGHT}px`,
          minHeight: `${DESCRIPTION_LINE_HEIGHT * descriptionLines}px`,
          color: 'text.primary',
          // Accessibility mode shows the whole description, so larger text
          // spacing can't cut it off (WCAG 1.4.12).
          ...(!theme.palette.accessibilityMode && {
            display: '-webkit-box',
            WebkitLineClamp: descriptionLines,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }),
        }}
      >
        {skeleton
          ? Array.from({ length: descriptionLines }, (_, i) => (
              <Skeleton
                key={i}
                variant="text"
                width={
                  i === descriptionLines - 1 ? SKELETON_LAST_LINE_WIDTH : '100%'
                }
                sx={delayedRevealSx}
              />
            ))
          : (description ?? '')}
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
          fontSize: rem(14),
          lineHeight: `${RELATIONS_LINE_HEIGHT}px`,
          minHeight: `${RELATIONS_LINE_HEIGHT}px`,
          color: 'text.secondary',
        }}
      >
        {relations.map(relation =>
          skeleton ? (
            <TextSlot key={relation.key}>
              <Relation relation={relation} />
            </TextSlot>
          ) : (
            <Relation key={relation.key} relation={relation} />
          )
        )}
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
                <SkeletonSlot variant="circular">
                  <Avatar
                    src={userAvatar}
                    sx={{ width: rem(20), height: rem(20), fontSize: rem(11) }}
                  >
                    {!userAvatar ? firstName[0].toUpperCase() : undefined}
                  </Avatar>
                </SkeletonSlot>
                {slot(firstName)}
              </>
            )}
          </Box>
          {footerAction ? (
            <SkeletonSlot>
              <Box onClick={e => e.stopPropagation()}>{footerAction}</Box>
            </SkeletonSlot>
          ) : (
            slot(updatedText)
          )}
        </Box>
      )}
    </Box>
  );
}
