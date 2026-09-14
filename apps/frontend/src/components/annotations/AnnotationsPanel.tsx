'use client';

import React, { useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { formatDistanceToNow } from 'date-fns';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import StatusChip from '@/components/common/StatusChip';
import { MentionText } from '@/components/common/MentionTextInput';
import { DeleteModal } from '@/components/common/DeleteModal';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isPassedStatusName } from '@/utils/test-result-status';
import {
  useAnnotationMutations,
  useEntityAnnotations,
} from '@/hooks/useAnnotations';
import type {
  Annotation,
  AnnotationEntityType,
} from '@/utils/api-client/interfaces/annotation';
import { ANNOTATION_COPY } from './annotation-copy';

/** The automated verdict, shown beside the human one so the difference is visible. */
export interface AutomatedVerdict {
  passed: boolean;
  label: string;
  /** e.g. "3/4" when the verdict comes from counting metrics. */
  count?: string;
}

export interface AnnotationsPanelProps {
  entityType: AnnotationEntityType;
  /** Undefined while the parent is still loading; the panel just shows empty. */
  entityId: string | undefined;
  automatedStatus: AutomatedVerdict;
  currentUserId: string;
  /** From the parent's `matches_annotation`: the human verdict disagrees. */
  hasConflict?: boolean;
  /** Shown when nothing annotates the entity itself but a metric is annotated. */
  metricVerdictLabel?: string | null;
  /** Opens the create surface. Rendered by the caller, which owns the drawer. */
  onCreate?: () => void;
  /** Called after any write, for parents that live outside react-query. */
  onChanged?: () => void;
}

function verdictDisplay(statusName: string): {
  passed: boolean;
  label: string;
} {
  const name = statusName.toLowerCase();
  return {
    passed: isPassedStatusName(statusName),
    label: name === 'fail' ? 'Failed' : name === 'pass' ? 'Passed' : statusName,
  };
}

function relativeTime(value: string): string {
  try {
    return formatDistanceToNow(new Date(value), { addSuffix: true }).toUpperCase();
  } catch {
    return 'N/A';
  }
}

/**
 * The annotations on one entity: the human verdict beside the automated one,
 * a conflict banner, and the list with resolve and delete.
 *
 * Rows are fetched per entity rather than read off the parent payload, so they
 * arrive with their own `permitted_actions` and each row can be gated on
 * itself. The parent still carries `annotation_summary` for grids and
 * indicators, which stay synchronous.
 */
export default function AnnotationsPanel({
  entityType,
  entityId,
  automatedStatus,
  currentUserId,
  hasConflict = false,
  metricVerdictLabel = null,
  onCreate,
  onChanged,
}: AnnotationsPanelProps) {
  const theme = useTheme();
  const [showOthers, setShowOthers] = useState(false);
  const [toDelete, setToDelete] = useState<Annotation | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const { annotations } = useEntityAnnotations(entityType, entityId);
  const { remove, setResolved } = useAnnotationMutations(entityType, entityId, {
    parentInvalidate: onChanged,
  });

  const canCreate = onCreate !== undefined;

  const sorted = useMemo(
    () =>
      [...annotations].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    [annotations]
  );
  const mine = useMemo(
    () => sorted.filter(a => String(a.user_id) === currentUserId),
    [sorted, currentUserId]
  );
  const others = useMemo(
    () => sorted.filter(a => String(a.user_id) !== currentUserId),
    [sorted, currentUserId]
  );

  // Once the user has their own annotation, show everyone's. The toggle only
  // matters before they have annotated.
  const visible = mine.length > 0 || showOthers ? sorted : mine;

  const entityLevel = useMemo(
    () => sorted.find(a => a.target_type === entityLevelTarget(entityType)),
    [sorted, entityType]
  );

  const handleToggleResolved = async (annotation: Annotation) => {
    try {
      setResolvingId(annotation.id);
      await setResolved(annotation.id, !annotation.resolved);
    } finally {
      setResolvingId(null);
    }
  };

  const handleConfirmDelete = async () => {
    if (!toDelete) return;
    try {
      setDeleting(true);
      await remove(toDelete.id);
      setToDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box
        sx={{ display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.primary">
            Automated:
          </Typography>
          <StatusChip
            passed={automatedStatus.passed}
            label={
              automatedStatus.count
                ? `${automatedStatus.label} ${automatedStatus.count}`
                : automatedStatus.label
            }
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.primary">
            {ANNOTATION_COPY.humanVerdictLabel}
          </Typography>
          {entityLevel?.status?.name ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <StatusChip
                {...verdictDisplay(entityLevel.status.name)}
                size="small"
                variant="outlined"
              />
              {hasConflict && (
                <Chip
                  icon={
                    <WarningAmberIcon sx={{ fontSize: '14px !important' }} />
                  }
                  label="Conflict"
                  size="small"
                  color="error"
                  variant="outlined"
                  sx={{
                    borderRadius: BORDER_RADIUS.pill,
                    '& .MuiChip-icon': { color: 'error.main' },
                  }}
                />
              )}
            </Box>
          ) : metricVerdictLabel ? (
            <StatusChip
              passed={isPassedStatusName(metricVerdictLabel)}
              label={`${verdictDisplay(metricVerdictLabel).label} (metric)`}
              size="small"
              variant="outlined"
            />
          ) : (
            <Chip
              label={ANNOTATION_COPY.noneChip}
              size="small"
              variant="outlined"
              sx={{ borderRadius: BORDER_RADIUS.pill }}
            />
          )}
        </Box>
      </Box>

      {hasConflict && (
        <Box
          sx={{
            bgcolor: t =>
              alpha(
                t.palette.warning.main,
                t.palette.mode === 'light' ? 0.08 : 0.16
              ),
            border: '1px solid',
            borderColor: 'warning.main',
            borderRadius: BORDER_RADIUS.xs,
            px: '30px',
            py: '12px',
            display: 'flex',
            alignItems: 'flex-start',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ pr: '12px', py: '4px', flexShrink: 0 }}>
            <WarningAmberIcon sx={{ fontSize: 18, color: 'warning.main' }} />
          </Box>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              py: '8px',
              flex: '1 0 0',
            }}
          >
            <Typography
              sx={{
                color: 'text.primary',
                fontWeight: 700,
                fontSize: 14,
                lineHeight: '20px',
              }}
            >
              {ANNOTATION_COPY.conflictTitle}
            </Typography>
            <Typography
              sx={{ color: 'text.secondary', fontSize: 13, lineHeight: '18px' }}
            >
              {ANNOTATION_COPY.conflictBody}
            </Typography>
          </Box>
        </Box>
      )}

      {sorted.length === 0 ? (
        <EmptyStateCard
          title={ANNOTATION_COPY.emptyNone}
          onCreate={canCreate ? onCreate : undefined}
        />
      ) : mine.length === 0 && !showOthers ? (
        <EmptyStateCard
          title={ANNOTATION_COPY.emptyMine}
          onCreate={canCreate ? onCreate : undefined}
          showOthersCount={others.length}
          onShowOthers={() => setShowOthers(true)}
        />
      ) : (
        <Paper
          variant="outlined"
          sx={{
            boxShadow: ELEVATION.xs,
            borderRadius: BORDER_RADIUS.md,
            overflow: 'hidden',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 3,
              pt: 3,
              pb: 2,
            }}
          >
            <Typography variant="h6" color="primary" fontWeight={600}>
              {ANNOTATION_COPY.sectionTitle}
            </Typography>
            {canCreate && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={onCreate}
                sx={{ '& .MuiSvgIcon-root': { color: 'primary.main' } }}
              >
                Create
              </Button>
            )}
          </Box>

          <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}>
            {visible.map(annotation => {
              const display = verdictDisplay(annotation.status?.name ?? '');
              const canUpdate = can(annotation, Capability.Annotation.UPDATE);
              const isResolving = resolvingId === annotation.id;
              const name = annotation.user?.name ?? '';
              return (
                <Box
                  key={annotation.id}
                  sx={{ px: 3, py: 2, opacity: annotation.resolved ? 0.7 : 1 }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      mb: 1.5,
                    }}
                  >
                    <Box
                      sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}
                    >
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          fontSize: 12,
                          bgcolor: 'primary.main',
                        }}
                      >
                        {name.charAt(0).toUpperCase()}
                      </Avatar>
                      <Typography variant="body2" fontWeight={700}>
                        {name}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ letterSpacing: 0.5 }}
                      >
                        {relativeTime(annotation.updated_at)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {annotation.resolved && (
                        <Chip
                          size="small"
                          label="Resolved"
                          variant="outlined"
                          sx={{
                            height: 24,
                            fontSize: t => t.typography.caption.fontSize,
                            borderRadius: BORDER_RADIUS.pill,
                            borderColor: 'success.main',
                            color: 'success.main',
                          }}
                        />
                      )}
                      <StatusChip
                        passed={display.passed}
                        label={display.label}
                        size="small"
                        variant="outlined"
                      />
                      {canUpdate && (
                        <Button
                          size="small"
                          variant="text"
                          disabled={isResolving}
                          onClick={e => {
                            e.stopPropagation();
                            void handleToggleResolved(annotation);
                          }}
                          sx={{
                            minWidth: 0,
                            px: 1,
                            textTransform: 'none',
                            fontWeight: 600,
                            fontSize: 13,
                            color: 'text.secondary',
                            '&:hover': {
                              color: 'text.primary',
                              bgcolor: 'action.hover',
                            },
                          }}
                        >
                          {annotation.resolved ? 'Reopen' : 'Resolve'}
                        </Button>
                      )}
                      {can(annotation, Capability.Annotation.DELETE) && (
                        <Tooltip title={ANNOTATION_COPY.deleteTooltip}>
                          <IconButton
                            size="small"
                            onClick={e => {
                              e.stopPropagation();
                              setToDelete(annotation);
                            }}
                            sx={{
                              color: 'text.secondary',
                              '& .MuiSvgIcon-root': { color: 'inherit' },
                              '&:hover': {
                                bgcolor: alpha(
                                  theme.palette.error.main,
                                  theme.palette.action.focusOpacity
                                ),
                                color: 'error.main',
                              },
                            }}
                          >
                            <DeleteOutlineIcon sx={{ fontSize: 18 }} />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </Box>

                  <Box
                    sx={{
                      bgcolor: theme.palette.greyscale.fieldSurface,
                      borderRadius: BORDER_RADIUS.xs,
                      p: 2,
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                    >
                      <MentionText text={annotation.comments ?? ''} />
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Paper>
      )}

      <DeleteModal
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        onConfirm={handleConfirmDelete}
        isLoading={deleting}
        title={ANNOTATION_COPY.deleteTitle}
        itemType="annotation"
        message={ANNOTATION_COPY.deleteMessage}
        confirmButtonText={ANNOTATION_COPY.deleteTitle}
        showTopBorder={true}
      />
    </Box>
  );
}

function entityLevelTarget(entityType: AnnotationEntityType): string {
  return entityType === 'TestResult'
    ? 'test_result'
    : entityType === 'Trace'
      ? 'trace'
      : 'test';
}

interface EmptyStateCardProps {
  title: string;
  /** Omit to hide the create button (the caller decides who may annotate). */
  onCreate?: () => void;
  showOthersCount?: number;
  onShowOthers?: () => void;
}

function EmptyStateCard({
  title,
  onCreate,
  showOthersCount,
  onShowOthers,
}: EmptyStateCardProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 4,
        boxShadow: ELEVATION.xs,
        borderRadius: BORDER_RADIUS.md,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        textAlign: 'center',
      }}
    >
      <InfoOutlinedIcon sx={{ fontSize: 32, color: 'primary.main' }} />
      <Typography variant="h6" color="primary" fontWeight={600}>
        {title}
      </Typography>
      <Typography variant="body2">{ANNOTATION_COPY.emptyBody}</Typography>
      {onCreate && (
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={onCreate}
          sx={{ borderRadius: BORDER_RADIUS.md }}
        >
          {ANNOTATION_COPY.createButton}
        </Button>
      )}
      {showOthersCount !== undefined && showOthersCount > 0 && onShowOthers && (
        <Button
          variant="text"
          color="primary"
          onClick={onShowOthers}
          sx={{ textTransform: 'none', textDecoration: 'underline' }}
        >
          {ANNOTATION_COPY.showOthers(showOthersCount)}
        </Button>
      )}
    </Paper>
  );
}
