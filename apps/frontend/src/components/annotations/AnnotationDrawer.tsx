'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControlLabel,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import { findStatusByCategory } from '@/utils/test-result-status';
import { EntityType } from '@/types/entity-type';
import MentionTextInput, {
  MentionOption,
  inferAnnotationTarget,
  InferredTarget,
} from '@/components/common/MentionTextInput';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { useAnnotationMutations } from '@/hooks/useAnnotations';
import {
  ENTITY_LEVEL_TARGETS,
  type Annotation,
  type AnnotationEntityType,
} from '@/utils/api-client/interfaces/annotation';
import { ANNOTATION_COPY } from './annotation-copy';

/** Comments shorter than this are rejected: a bare verdict explains nothing. */
const MIN_COMMENT_LENGTH = 10;

/**
 * Whether the comment is good enough to save.
 *
 * A new annotation must carry a real reason. An existing one only has to not
 * get worse: metric tuning and explorer labels record a verdict with no
 * comment at all, and holding those to the minimum would make them
 * permanently un-editable, verdict included.
 */
function commentIsAcceptable(
  comment: string,
  original: string | null | undefined
): boolean {
  const trimmed = comment.trim();
  if (trimmed.length >= MIN_COMMENT_LENGTH) return true;
  return original !== undefined && trimmed === (original ?? '').trim();
}

export interface AnnotationDrawerProps {
  open: boolean;
  onClose: () => void;
  entityType: AnnotationEntityType;
  entityId: string | undefined;
  /** Which status rows the verdict picker offers. */
  statusEntityType?: EntityType;
  onSaved: () => void | Promise<void>;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  /**
   * Edit this annotation instead of creating one. Its verdict and comment seed
   * the form, and saving PUTs rather than POSTs.
   */
  annotation?: Annotation | null;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  /**
   * Optional block above the picker, e.g. the automated verdict being judged.
   * Takes the inferred target, since what is being judged depends on it.
   */
  renderContext?: (target: InferredTarget) => React.ReactNode;
}

/**
 * Records one annotation on any entity, or edits one that exists.
 *
 * The target comes from the comment: an `@metric` or `@turn` mention makes this
 * a metric or turn annotation, and its absence makes it entity-level. That is
 * why the comment is required rather than optional.
 */
export default function AnnotationDrawer({
  open,
  onClose,
  entityType,
  entityId,
  statusEntityType = EntityType.TEST_RESULT,
  onSaved,
  initialComment,
  initialStatus,
  annotation = null,
  mentionableMetrics = [],
  mentionableTurns = [],
  renderContext,
}: AnnotationDrawerProps) {
  const isEditing = annotation !== null;
  const { status: sessionStatus } = useSession();
  const [selectedStatusId, setSelectedStatusId] = useState('');
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [resolved, setResolved] = useState(false);

  const { create, update } = useAnnotationMutations(entityType, entityId);

  const inferredTarget: InferredTarget = useMemo(
    () => inferAnnotationTarget(comment, ENTITY_LEVEL_TARGETS[entityType]),
    [comment, entityType]
  );

  const passStatus = useMemo(
    () => findStatusByCategory(statuses, 'passed'),
    [statuses]
  );
  const failStatus = useMemo(
    () => findStatusByCategory(statuses, 'failed'),
    [statuses]
  );

  useEffect(() => {
    const fetchStatuses = async () => {
      if (!open || !isAuthenticated(sessionStatus) || statuses.length > 0) {
        return;
      }
      try {
        setLoadingStatuses(true);
        const fetched = await new ApiClientFactory()
          .getStatusClient()
          .getStatuses({ entity_type: statusEntityType });
        setStatuses(fetched);
      } catch (_err) {
        setError('Failed to load status options');
      } finally {
        setLoadingStatuses(false);
      }
    };
    fetchStatuses();
  }, [open, statuses.length, sessionStatus, statusEntityType]);

  // Reset on open only: a parent state reset must not clear a form the user is
  // actively filling, which is why initialComment/initialStatus are excluded.
  useEffect(() => {
    if (!open) return;
    setComment(annotation?.comments ?? initialComment ?? '');
    setError('');
    setSelectedStatusId(annotation ? String(annotation.status_id) : '');
    setResolved(Boolean(annotation?.resolved));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open only
  }, [open]);

  useEffect(() => {
    if (!open || selectedStatusId || statuses.length === 0 || !initialStatus) {
      return;
    }
    const matching = findStatusByCategory(statuses, initialStatus);
    if (matching) setSelectedStatusId(String(matching.id));
  }, [open, statuses, initialStatus, selectedStatusId]);

  const commentOk = commentIsAcceptable(
    comment,
    annotation ? (annotation.comments ?? '') : undefined
  );

  const handleSave = async () => {
    const trimmed = comment.trim();
    if (!commentOk) {
      setError(ANNOTATION_COPY.commentTooShort(MIN_COMMENT_LENGTH));
      return;
    }
    if (!selectedStatusId) {
      setError(ANNOTATION_COPY.verdictRequired);
      return;
    }
    if (!entityId || !isAuthenticated(sessionStatus)) return;

    try {
      setSubmitting(true);
      setError('');
      // Through the mutation hook, not the client: it invalidates the entity
      // list this drawer's panel reads. The QueryClient runs a 5 minute
      // staleTime with refetchOnWindowFocus off, so without that the saved
      // annotation would be missing from the list until it expired.
      if (annotation) {
        await update(annotation.id, {
          status_id: selectedStatusId,
          comments: trimmed,
          target: inferredTarget,
          resolved,
        });
      } else {
        await create({
          statusId: selectedStatusId,
          comments: trimmed,
          target: inferredTarget,
        });
      }
      await onSaved();
      onClose();
    } catch (_err) {
      setError(ANNOTATION_COPY.saveFailed);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    setComment('');
    setError('');
    onClose();
  };

  if (!entityId) return null;

  const selectedSx = (color: 'success' | 'error') => ({
    flex: 1,
    gap: 1,
    '&.Mui-selected': {
      bgcolor: `${color}.main`,
      color: 'common.white',
      '&:hover': { bgcolor: `${color}.dark` },
      '& .MuiSvgIcon-root': { color: 'common.white' },
    },
  });

  return (
    <BaseDrawer
      open={open}
      onClose={handleCancel}
      title={
        isEditing ? ANNOTATION_COPY.editTitle : ANNOTATION_COPY.drawerTitle
      }
      onSave={handleSave}
      anchor="right"
      saveButtonText="Save"
      saveDisabled={
        !selectedStatusId || !commentOk || submitting || loadingStatuses
      }
      error={error}
      loading={submitting || loadingStatuses}
    >
      {renderContext?.(inferredTarget)}

      <Box>
        <Typography
          variant="body2"
          sx={theme => ({
            mb: 1,
            fontWeight: theme.typography.fontWeightMedium,
            color: 'text.secondary',
          })}
        >
          {ANNOTATION_COPY.verdictLabel}
        </Typography>
        <ToggleButtonGroup
          value={selectedStatusId}
          exclusive
          onChange={(_, val) => {
            if (val !== null) {
              setSelectedStatusId(val);
              setError('');
            }
          }}
          fullWidth
          disabled={loadingStatuses}
        >
          {passStatus && (
            <ToggleButton
              value={String(passStatus.id)}
              sx={selectedSx('success')}
            >
              <CheckCircleOutlineIcon fontSize="small" />
              Pass
            </ToggleButton>
          )}
          {failStatus && (
            <ToggleButton
              value={String(failStatus.id)}
              sx={selectedSx('error')}
            >
              <CancelOutlinedIcon fontSize="small" />
              Fail
            </ToggleButton>
          )}
        </ToggleButtonGroup>
      </Box>

      {isEditing && (
        <FormControlLabel
          control={
            <Switch
              checked={resolved}
              onChange={event => setResolved(event.target.checked)}
            />
          }
          label={ANNOTATION_COPY.resolvedLabel}
        />
      )}

      <MentionTextInput
        label="Comment"
        value={comment}
        onChange={val => {
          setComment(val);
          setError('');
        }}
        placeholder={ANNOTATION_COPY.commentPlaceholder}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
        error={!!error && !selectedStatusId}
        helperText={
          commentOk
            ? ANNOTATION_COPY.commentHelp
            : ANNOTATION_COPY.commentCounter(
                comment.trim().length,
                MIN_COMMENT_LENGTH
              )
        }
        minRows={4}
      />
    </BaseDrawer>
  );
}
