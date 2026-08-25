'use client';

import * as React from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Typography,
  useTheme,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import EditableSection from '@/components/common/EditableSection';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { isMultiTurnTest } from '@/constants/test-types';
import type {
  EvaluationContract,
  EvaluationContractStatus,
} from '@/utils/api-client/interfaces/evaluation-contract';

/**
 * Shows how a multi-turn test's wording was read for scoring.
 *
 * A test's goal is free text, and the same intent gets written in opposite directions. The
 * backend normalizes it into statements about the target before anything is scored, so this
 * panel is where a reviewer can catch a misreading before it turns into a wrong verdict. It is
 * read-only on purpose: the authored fields stay the single source of truth, and a bad reading
 * is fixed by rewriting the goal or restrictions, not by editing the reading.
 */

const NO_OP_DRAFT = {} as const;

interface TestInterpretationCardProps {
  test: TestDetail;
}

function BehaviourList({
  label,
  items,
  emptyHint,
}: {
  label: string;
  items: string[];
  emptyHint: string;
}) {
  const theme = useTheme();

  return (
    <Box>
      <Typography
        variant="overline"
        sx={{ color: 'text.secondary', fontWeight: 600 }}
      >
        {label}
      </Typography>
      {items.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'text.disabled' }}>
          {emptyHint}
        </Typography>
      ) : (
        <List dense disablePadding>
          {items.map(item => (
            <ListItem
              key={item}
              disableGutters
              sx={{ py: theme.spacing(0.25) }}
            >
              <ListItemText
                primary={item}
                primaryTypographyProps={{ variant: 'body2' }}
              />
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
}

function ContractBody({ contract }: { contract: EvaluationContract }) {
  const theme = useTheme();

  return (
    <Box
      sx={{ display: 'flex', flexDirection: 'column', gap: theme.spacing(2.5) }}
    >
      <Box sx={{ display: 'flex', gap: theme.spacing(1), flexWrap: 'wrap' }}>
        <Chip
          size="small"
          variant="outlined"
          color={contract.adversarial ? 'warning' : 'default'}
          label={contract.adversarial ? 'Adversarial' : 'Cooperative'}
        />
        <Chip
          size="small"
          variant="outlined"
          label={`Confidence ${Math.round(contract.confidence * 100)}%`}
        />
      </Box>

      <BehaviourList
        label="The target must"
        items={contract.required_behavior}
        emptyHint="Nothing required — this test only checks for prohibited behaviour."
      />
      <BehaviourList
        label="The target must not"
        items={contract.prohibited_behavior}
        emptyHint="Nothing prohibited — this test only checks for required behaviour."
      />

      <Box>
        <Typography
          variant="overline"
          sx={{ color: 'text.secondary', fontWeight: 600 }}
        >
          The simulated user will try to
        </Typography>
        <Typography variant="body2">
          {contract.simulated_user_objective || '—'}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Drives the conversation. Never scored.
        </Typography>
      </Box>

      {contract.source_notes.length > 0 && (
        <Box>
          <Typography
            variant="overline"
            sx={{ color: 'text.secondary', fontWeight: 600 }}
          >
            How your wording was read
          </Typography>
          <List dense disablePadding>
            {contract.source_notes.map(note => (
              <ListItem
                key={`${note.source_field}-${note.note}`}
                disableGutters
                sx={{ py: theme.spacing(0.25) }}
              >
                <ListItemText
                  primary={note.note}
                  secondary={note.source_field}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}
    </Box>
  );
}

export default function TestInterpretationCard({
  test,
}: TestInterpretationCardProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const canUpdate = useCan(Capability.Test.UPDATE);

  const [status, setStatus] = React.useState<EvaluationContractStatus | null>(
    null
  );
  const [isLoading, setIsLoading] = React.useState(true);
  const [isInterpreting, setIsInterpreting] = React.useState(false);

  const isMultiTurn = isMultiTurnTest(test.test_type?.type_value);

  const load = React.useCallback(async () => {
    try {
      const client = new ApiClientFactory().getTestsClient();
      setStatus(await client.getTestInterpretation(test.id));
    } catch {
      notifications.show('Could not load the test interpretation', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsLoading(false);
    }
  }, [test.id, notifications]);

  React.useEffect(() => {
    if (isMultiTurn) {
      load();
    } else {
      setIsLoading(false);
    }
  }, [isMultiTurn, load]);

  const handleInterpret = React.useCallback(async () => {
    setIsInterpreting(true);
    try {
      const client = new ApiClientFactory().getTestsClient();
      const next = await client.interpretTest(test.id, { force: true });
      setStatus(next);
      notifications.show(
        next.usable
          ? 'Test interpreted'
          : 'Interpreted, but the result cannot be used for scoring',
        {
          severity: next.usable ? 'success' : 'warning',
          autoHideDuration: 4000,
        }
      );
    } catch {
      notifications.show('Could not interpret this test', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsInterpreting(false);
    }
  }, [test.id, notifications]);

  if (!isMultiTurn) {
    return null;
  }

  const contract = status?.contract ?? null;
  const showStale = Boolean(status?.interpreted && !status.is_current);

  return (
    <EditableSection
      editable={false}
      title="How this test is interpreted"
      subtitle="Scoring uses this reading of your goal and restrictions, not the wording itself."
      headerActions={
        canUpdate ? (
          <Button
            size="small"
            startIcon={
              isInterpreting ? (
                <CircularProgress size={16} />
              ) : (
                <RefreshIcon fontSize="small" />
              )
            }
            onClick={handleInterpret}
            disabled={isInterpreting || isLoading}
          >
            {status?.interpreted ? 'Re-interpret' : 'Interpret now'}
          </Button>
        ) : undefined
      }
      initialValue={NO_OP_DRAFT}
      onSave={async () => undefined}
    >
      {() => (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: theme.spacing(2),
          }}
        >
          {isLoading && <CircularProgress size={20} />}

          {!isLoading && showStale && (
            <Alert severity="warning">
              This test was edited after it was last interpreted. Re-interpret
              it so scoring matches the current wording.
            </Alert>
          )}

          {!isLoading && status && !status.usable && status.reason && (
            <Alert severity={status.interpreted ? 'error' : 'info'}>
              {status.reason}
              {status.interpreted &&
                ' Runs of this test will report an error until it is resolved.'}
            </Alert>
          )}

          {!isLoading && contract && <ContractBody contract={contract} />}
        </Box>
      )}
    </EditableSection>
  );
}
