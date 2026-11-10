'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Badge, Box, Button, TextField, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { Fab } from '@/components/common/Fab';
import { BORDER_RADIUS } from '@/styles/theme';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type {
  RequirementReviewHint,
  RequirementUpdate,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import type { UUID } from 'crypto';
import {
  hintKey,
  hintUpdate,
  isReviewOutdated,
  requirementTextHash,
  ruleHints,
  type RuleHintId,
} from './requirement-suggestions';
import { useRequirementActions } from './useRequirementActions';

const RULE_ACTION_LABELS: Partial<Record<RuleHintId, string>> = {
  no_source: 'Add source',
  no_examples: 'View examples',
  no_metric: 'Link metric',
};

const ICON_SIZE = 22;

/** Heading of a drawer section, with an optional action on the right. */
function SectionHeader({
  headline,
  caption,
  action,
}: {
  headline: string;
  caption: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 1.5,
        pb: 1.25,
        borderBottom: 1,
        borderColor: theme => theme.palette.greyscale.border,
      }}
    >
      <FormSectionDivider headline={headline} descriptiveText={caption} />
      {action}
    </Box>
  );
}

function WarnIcon() {
  return (
    <Box
      aria-hidden
      sx={{
        width: ICON_SIZE,
        height: ICON_SIZE,
        flexShrink: 0,
        borderRadius: '50%',
        display: 'grid',
        placeItems: 'center',
        typography: 'caption',
        fontWeight: 700,
        bgcolor: theme => alpha(theme.palette.warning.main, 0.14),
        color: 'warning.main',
      }}
    >
      !
    </Box>
  );
}

function MissingIcon() {
  return (
    <Box
      aria-hidden
      sx={{
        width: ICON_SIZE,
        height: ICON_SIZE,
        flexShrink: 0,
        borderRadius: '50%',
        border: 1.5,
        borderStyle: 'dashed',
        borderColor: theme => theme.palette.greyscale.border,
      }}
    />
  );
}

interface HintCardProps {
  hint: RequirementReviewHint;
  /** Hidden for an outdated review: the words may no longer be there. */
  showQuote: boolean;
  /** The update "Use suggestion" makes, or null when there is none. */
  changes: RequirementUpdate | null;
  /** Today's description, the starting text for "Edit description". */
  description: string;
  canEdit: boolean;
  busy: boolean;
  onApply: (changes: RequirementUpdate) => Promise<boolean>;
  onDismiss: () => void;
}

/**
 * One AI hint. "Edit first" and "Edit description" open a field inside the
 * card; Save writes straight away, like "Use suggestion".
 */
function HintCard({
  hint,
  showQuote,
  changes,
  description,
  canEdit,
  busy,
  onApply,
  onDismiss,
}: HintCardProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const editing = draft !== null;
  const rewrite = changes ? hint.suggestion?.trim() : null;

  const save = async () => {
    if (draft === null) return;
    // Nothing changed: close the editor without writing.
    if (draft === description) {
      setDraft(null);
      return;
    }
    if (await onApply({ description: draft })) setDraft(null);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.25,
        p: 1.5,
        border: 1,
        borderRadius: BORDER_RADIUS.sm,
        borderColor: editing
          ? 'primary.main'
          : theme => theme.palette.greyscale.border,
        boxShadow: theme =>
          editing
            ? `0 0 0 3px ${alpha(theme.palette.primary.main, 0.18)}`
            : 'none',
      }}
    >
      <WarnIcon />
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
        }}
      >
        <Typography variant="body1" sx={{ fontWeight: 500 }}>
          {hint.message}
        </Typography>
        {showQuote && hint.quote && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              borderLeft: 3,
              borderColor: 'warning.main',
              pl: 1,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {hint.quote}
          </Typography>
        )}

        {editing ? (
          <>
            <TextField
              label="New description"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              multiline
              minRows={3}
              autoFocus
              fullWidth
              sx={{ mt: 1 }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
              <Button
                size="small"
                color="inherit"
                onClick={() => setDraft(null)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button
                size="small"
                onClick={() => void save()}
                disabled={busy || !draft.trim()}
              >
                Save
              </Button>
            </Box>
          </>
        ) : (
          <>
            {rewrite && (
              <Box
                sx={{
                  bgcolor: theme => theme.palette.greyscale.surface2,
                  borderRadius: BORDER_RADIUS.xs,
                  px: 1.25,
                  py: 1,
                }}
              >
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    display: 'block',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    fontWeight: 600,
                  }}
                >
                  Suggested rewrite
                </Typography>
                <Typography variant="body2">{rewrite}</Typography>
              </Box>
            )}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, ml: -1 }}>
              {changes && (
                <Button
                  size="small"
                  disabled={busy}
                  onClick={() => void onApply(changes)}
                >
                  Use suggestion
                </Button>
              )}
              {canEdit && (
                <Button
                  size="small"
                  disabled={busy}
                  onClick={() =>
                    setDraft(
                      changes?.description !== undefined
                        ? (changes.description ?? '')
                        : description
                    )
                  }
                >
                  {changes ? 'Edit first' : 'Edit description'}
                </Button>
              )}
              <Button size="small" color="inherit" onClick={onDismiss}>
                Dismiss
              </Button>
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}

interface RequirementSuggestionsFabProps {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
  onRuleAction: (id: RuleHintId) => void;
}

/**
 * Page FAB that opens the Suggestions drawer: the page's own checks plus the
 * stored AI review. The badge counts what is still open; dismissing only hides
 * a hint until the page reloads.
 */
export default function RequirementSuggestionsFab({
  requirement,
  onUpdated,
  onRuleAction,
}: RequirementSuggestionsFabProps) {
  const notifications = useNotifications();
  const canEdit = useCan(Capability.Requirement.UPDATE);
  const { refresh, update } = useRequirementActions(
    requirement.id as UUID,
    onUpdated
  );
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [reviewing, setReviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [textHash, setTextHash] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void requirementTextHash(requirement.name, requirement.description).then(
      hash => {
        if (!cancelled) setTextHash(hash);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [requirement.name, requirement.description]);

  const review = requirement.review ?? null;
  const outdated = isReviewOutdated(review, textHash);
  const dismiss = (key: string) => setDismissed(prev => new Set(prev).add(key));

  const aiHints = useMemo(
    () => (review?.hints ?? []).filter(h => !dismissed.has(`ai:${hintKey(h)}`)),
    [review, dismissed]
  );
  const rules = ruleHints(requirement).filter(
    h => !dismissed.has(`rule:${h.id}`)
  );
  const total = aiHints.length + rules.length;

  const handleReview = async () => {
    setReviewing(true);
    try {
      await new RequirementClient().reviewRequirement(requirement.id as UUID);
      await refresh();
    } catch (err) {
      notifications.show(
        err instanceof Error
          ? `Review failed: ${err.message}`
          : 'Review failed. Please try again.',
        { severity: 'error' }
      );
    } finally {
      setReviewing(false);
    }
  };

  /** Writes the change and closes the hint. Returns whether it worked. */
  const apply = async (
    hint: RequirementReviewHint,
    changes: RequirementUpdate
  ): Promise<boolean> => {
    setApplying(true);
    try {
      await update(changes);
      dismiss(`ai:${hintKey(hint)}`);
      return true;
    } catch {
      notifications.show('Failed to save the change', { severity: 'error' });
      return false;
    } finally {
      setApplying(false);
    }
  };

  const reviewCaption = review ? (
    <>
      Generation model ·{' '}
      {formatDistanceToNow(new Date(review.reviewed_at), { addSuffix: true })}
      {outdated && (
        <Box component="span" sx={{ color: 'warning.main' }}>
          {' '}
          · outdated, the text changed since
        </Box>
      )}
    </>
  ) : (
    'Not reviewed yet. A review asks your generation model for vague wording and missing details.'
  );

  return (
    <>
      <Badge
        badgeContent={total}
        invisible={total === 0}
        overlap="circular"
        // Outlined so it reads on both the primary FAB and the page behind it,
        // and above the FAB, whose own z-index would otherwise cover it.
        sx={{
          '& .MuiBadge-badge': {
            bgcolor: 'background.paper',
            color: 'primary.main',
            border: 1,
            borderColor: 'primary.main',
            fontWeight: 700,
            zIndex: theme => theme.zIndex.fab + 1,
          },
        }}
      >
        <Fab
          icon={<LightbulbOutlinedIcon />}
          tooltip="Suggestions"
          aria-label={total > 0 ? `Suggestions (${total} open)` : 'Suggestions'}
          onClick={() => setOpen(true)}
        />
      </Badge>

      <BaseDrawer
        open={open}
        onClose={() => setOpen(false)}
        title="Suggestions"
        closeButtonText="Close"
      >
        {/* The intro shares a box with the first section: a negative margin
            would pull it above the drawer's scroll area and clip it. */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            flexShrink: 0,
          }}
        >
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Ways to make this requirement clearer and easier to test. Nothing
            changes until you apply it.
          </Typography>
          <SectionHeader
            headline="AI review"
            caption={reviewCaption}
            action={
              canEdit ? (
                <Button
                  size="small"
                  onClick={() => void handleReview()}
                  disabled={reviewing}
                  sx={{ flexShrink: 0 }}
                >
                  {reviewing
                    ? 'Reviewing…'
                    : review
                      ? 'Review again'
                      : 'Review'}
                </Button>
              ) : undefined
            }
          />
          {aiHints.map(hint => (
            <HintCard
              key={`ai:${hintKey(hint)}`}
              hint={hint}
              showQuote={!outdated}
              changes={
                canEdit ? hintUpdate(hint, requirement.description) : null
              }
              description={requirement.description ?? ''}
              canEdit={canEdit}
              busy={applying}
              onApply={changes => apply(hint, changes)}
              onDismiss={() => dismiss(`ai:${hintKey(hint)}`)}
            />
          ))}
          {review && aiHints.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              Nothing to fix from the review.
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <SectionHeader
            headline="Missing"
            caption="Checked on this page, no model involved"
          />
          {rules.map(hint => {
            const label = RULE_ACTION_LABELS[hint.id];
            const showAction = label && (canEdit || hint.id !== 'no_source');
            return (
              <Box
                key={`rule:${hint.id}`}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.25,
                  py: 1.25,
                  borderBottom: 1,
                  borderColor: theme => theme.palette.greyscale.border,
                }}
              >
                <MissingIcon />
                <Typography variant="body1" sx={{ flex: 1, minWidth: 0 }}>
                  {hint.message}
                </Typography>
                {showAction && (
                  <Button
                    size="small"
                    onClick={() => {
                      setOpen(false);
                      onRuleAction(hint.id);
                    }}
                  >
                    {label}
                  </Button>
                )}
              </Box>
            );
          })}
          {rules.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ pt: 1.5 }}>
              Nothing missing.
            </Typography>
          )}
        </Box>
      </BaseDrawer>
    </>
  );
}
