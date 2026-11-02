'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  Badge,
  Box,
  Button,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import AddLinkIcon from '@mui/icons-material/AddLink';
import { AddIcon } from '@/components/icons';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { Fab } from '@/components/common/Fab';
import { drawerSectionSx } from '@/components/common/drawerFormFieldSx';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
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
import { useRequirementTypes } from '../../components/requirement-lookups';
import {
  hintKey,
  hintUpdate,
  isReviewOutdated,
  requirementTextHash,
  ruleHints,
  type RuleHintId,
} from './requirement-suggestions';
import { useRequirementActions } from './useRequirementActions';

const RULE_ACTIONS: Partial<
  Record<RuleHintId, { label: string; icon: React.ReactNode }>
> = {
  no_source: { label: 'Add source', icon: <AddIcon fontSize="small" /> },
  no_examples: {
    label: 'View examples',
    icon: <ArrowForwardIcon fontSize="small" />,
  },
  no_metric: { label: 'Link metric', icon: <AddLinkIcon fontSize="small" /> },
};

/** A row action, sized like the models drawer's row icon buttons. */
function RowAction({
  label,
  icon,
  onClick,
  disabled,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Tooltip title={label}>
      <span>
        <IconButton
          size="small"
          aria-label={label}
          onClick={onClick}
          disabled={disabled}
          color="primary"
        >
          {icon}
        </IconButton>
      </span>
    </Tooltip>
  );
}

/** One hint, laid out like the model drawer's settings rows. */
function HintRow({
  message,
  quote,
  suggestion,
  action,
  onDismiss,
}: {
  message: string;
  quote?: string | null;
  suggestion?: string | null;
  action?: React.ReactNode;
  onDismiss: () => void;
}) {
  return (
    <Box
      sx={{
        borderTop: 1,
        borderColor: theme => theme.palette.greyscale.border,
        py: 2.5,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.5,
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body1">{message}</Typography>
        {quote && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            In the description:{' '}
            <Box
              component="mark"
              sx={{
                bgcolor: 'warning.light',
                color: 'inherit',
                borderBottom: 2,
                borderColor: 'warning.main',
                borderBottomStyle: 'dotted',
              }}
            >
              {quote}
            </Box>
          </Typography>
        )}
        {suggestion && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Suggested: “{suggestion}”
          </Typography>
        )}
      </Box>
      {action}
      <Tooltip title="Dismiss">
        <IconButton size="small" onClick={onDismiss} aria-label="Dismiss">
          <CloseIcon fontSize="small" />
        </IconButton>
      </Tooltip>
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
  const { data: typeOptions = [] } = useRequirementTypes();
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

  const apply = async (
    hint: RequirementReviewHint,
    changes: RequirementUpdate
  ) => {
    setApplying(true);
    try {
      await update(changes);
      dismiss(`ai:${hintKey(hint)}`);
    } catch {
      notifications.show('Failed to apply the suggestion', {
        severity: 'error',
      });
    } finally {
      setApplying(false);
    }
  };

  const reviewLine = review
    ? `Reviewed with your generation model · ${formatDistanceToNow(
        new Date(review.reviewed_at),
        { addSuffix: true }
      )}`
    : 'Not reviewed yet. A review asks your generation model for vague wording and missing details.';

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
        <Box sx={drawerSectionSx}>
          <FormSectionDivider
            headline="AI review"
            descriptiveText={
              <>
                {reviewLine}
                {outdated && (
                  <Box component="span" sx={{ color: 'warning.main' }}>
                    {' '}
                    · outdated, the text changed since
                  </Box>
                )}
              </>
            }
          />
          {canEdit && (
            <Button
              size="small"
              variant="outlined"
              onClick={() => void handleReview()}
              disabled={reviewing}
              sx={[sectionEditButtonSx, { alignSelf: 'flex-start' }]}
            >
              {reviewing ? 'Reviewing…' : review ? 'Review again' : 'Review'}
            </Button>
          )}
          {(aiHints.length > 0 || review) && (
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              {aiHints.map(hint => {
                const changes = canEdit
                  ? hintUpdate(hint, requirement.description, typeOptions)
                  : null;
                const isType = hint.kind === 'suggest_type';
                return (
                  <HintRow
                    key={`ai:${hintKey(hint)}`}
                    message={hint.message}
                    // Quotes from an outdated review may no longer be there.
                    quote={outdated ? null : hint.quote}
                    suggestion={isType ? null : hint.suggestion}
                    action={
                      changes ? (
                        <RowAction
                          label={isType ? 'Set type' : 'Use suggestion'}
                          icon={<CheckIcon fontSize="small" />}
                          disabled={applying}
                          onClick={() => void apply(hint, changes)}
                        />
                      ) : undefined
                    }
                    onDismiss={() => dismiss(`ai:${hintKey(hint)}`)}
                  />
                );
              })}
              {review && aiHints.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  Nothing to fix from the review.
                </Typography>
              )}
            </Box>
          )}
        </Box>

        <Box sx={drawerSectionSx}>
          <FormSectionDivider
            headline="Checks"
            descriptiveText="What this requirement is still missing."
          />
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            {rules.map(hint => {
              const ruleAction = RULE_ACTIONS[hint.id];
              return (
                <HintRow
                  key={`rule:${hint.id}`}
                  message={hint.message}
                  action={
                    ruleAction && (canEdit || hint.id !== 'no_source') ? (
                      <RowAction
                        label={ruleAction.label}
                        icon={ruleAction.icon}
                        onClick={() => {
                          setOpen(false);
                          onRuleAction(hint.id);
                        }}
                      />
                    ) : undefined
                  }
                  onDismiss={() => dismiss(`rule:${hint.id}`)}
                />
              );
            })}
            {rules.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                All clear.
              </Typography>
            )}
          </Box>
        </Box>
      </BaseDrawer>
    </>
  );
}
