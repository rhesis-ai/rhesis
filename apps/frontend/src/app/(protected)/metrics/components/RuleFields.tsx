'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';
import {
  ARGUMENT_MATCH_LABELS,
  ATTRIBUTE_FIELD,
  CREATABLE_RULE_CLASSES,
  RESPONSE_MATCHES,
  RESPONSE_MATCH_LABELS,
  RULE_CLASSES,
  RULE_FIELDS,
  SIMILARITY_LABELS,
  SPAN_COUNT_FIELD,
  TRAJECTORY_MATCH_LABELS,
  describeRule,
  operatorTakesList,
  operatorTakesValue,
  operatorsFor,
  ruleDraftError,
  type RuleClass,
  type RuleDraft,
} from '@/utils/metric-rules';

interface RuleFieldsProps {
  draft: RuleDraft;
  onChange: (draft: RuleDraft) => void;
  /** The per-span targets, whose kinds a span count can be limited to. */
  spanKinds: MetricTargetChoice[];
  showErrors?: boolean;
  /** Whether the rule's form can still change; it can't once the metric exists. */
  allowClassChoice?: boolean;
}

/** The settings of a rule: what it reads, how it compares, and with what. */
export default function RuleFields({
  draft,
  onChange,
  spanKinds,
  showErrors = false,
  allowClassChoice = false,
}: RuleFieldsProps) {
  const id = React.useId();
  const set = (changes: Partial<RuleDraft>) =>
    onChange({ ...draft, ...changes });
  const error = showErrors ? ruleDraftError(draft) : null;
  const operators = operatorsFor(draft.field);

  const selectField = (field: string) => {
    const ops = operatorsFor(field);
    set({
      field,
      op: ops.some(o => o.value === draft.op) ? draft.op : ops[0].value,
    });
  };

  return (
    <Box>
      {allowClassChoice && (
        <Box
          sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }}
          role="radiogroup"
          aria-label="Rule"
        >
          {CREATABLE_RULE_CLASSES.map(choice => {
            const selected = choice.value === draft.ruleClass;
            return (
              <Chip
                key={choice.value}
                role="radio"
                aria-checked={selected}
                label={choice.label}
                clickable
                color={selected ? 'primary' : 'default'}
                variant={selected ? 'filled' : 'outlined'}
                onClick={() => set({ ruleClass: choice.value as RuleClass })}
              />
            );
          })}
        </Box>
      )}

      {draft.ruleClass === RULE_CLASSES.FIELD && (
        <>
          <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
            <FormControl sx={{ flex: 2, minWidth: theme => theme.spacing(25) }}>
              <InputLabel id={`${id}-field`}>Field</InputLabel>
              <Select
                labelId={`${id}-field`}
                label="Field"
                value={draft.field}
                onChange={e => selectField(e.target.value)}
              >
                {RULE_FIELDS.map(field => (
                  <MenuItem key={field.value} value={field.value}>
                    {field.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}>
              <InputLabel id={`${id}-op`}>Operator</InputLabel>
              <Select
                labelId={`${id}-op`}
                label="Operator"
                value={
                  operators.some(o => o.value === draft.op) ? draft.op : ''
                }
                onChange={e => set({ op: e.target.value })}
              >
                {operators.map(op => (
                  <MenuItem key={op.value} value={op.value}>
                    {op.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {operatorTakesValue(draft.op) && (
              <TextField
                sx={{ flex: 2, minWidth: theme => theme.spacing(25) }}
                label={operatorTakesList(draft.op) ? 'Values' : 'Value'}
                value={draft.value}
                onChange={e => set({ value: e.target.value })}
                helperText={
                  operatorTakesList(draft.op)
                    ? 'Separate values with commas'
                    : undefined
                }
              />
            )}
          </Box>

          {draft.field === ATTRIBUTE_FIELD && (
            <TextField
              fullWidth
              label="Attribute key"
              placeholder="rhesis.reported.metadata.confidence"
              value={draft.attributeKey}
              onChange={e => set({ attributeKey: e.target.value })}
              helperText="The span attribute to read, as the trace view shows it"
              sx={{ mb: 3 }}
            />
          )}

          {draft.field === SPAN_COUNT_FIELD && (
            <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
              <FormControl
                sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}
              >
                <InputLabel id={`${id}-span-kind`}>Count only</InputLabel>
                <Select
                  labelId={`${id}-span-kind`}
                  label="Count only"
                  value={draft.spanKind}
                  onChange={e => set({ spanKind: e.target.value })}
                >
                  <MenuItem value="">Every span</MenuItem>
                  {spanKinds.map(kind => (
                    <MenuItem key={kind.on} value={kind.on}>
                      {kind.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}
                label="Name"
                placeholder="e.g. issue_refund"
                value={draft.spanName}
                onChange={e => set({ spanName: e.target.value })}
                helperText="Only spans with this tool, agent or model name"
              />
            </Box>
          )}

          <FormControlLabel
            control={
              <Switch
                checked={draft.negate}
                onChange={e => set({ negate: e.target.checked })}
              />
            }
            label="Pass when this does not hold"
            sx={{ mb: 2 }}
          />
        </>
      )}

      {draft.ruleClass === RULE_CLASSES.RESPONSE && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <FormControl sx={{ flex: 2, minWidth: theme => theme.spacing(30) }}>
            <InputLabel id={`${id}-match`}>The output</InputLabel>
            <Select
              labelId={`${id}-match`}
              label="The output"
              value={draft.match}
              onChange={e => set({ match: e.target.value })}
            >
              {Object.entries(RESPONSE_MATCH_LABELS).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {draft.match === RESPONSE_MATCHES.SIMILAR && (
            <>
              <FormControl
                sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}
              >
                <InputLabel id={`${id}-similarity`}>Measured by</InputLabel>
                <Select
                  labelId={`${id}-similarity`}
                  label="Measured by"
                  value={draft.similarity}
                  onChange={e => set({ similarity: e.target.value })}
                >
                  {Object.entries(SIMILARITY_LABELS).map(([value, label]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}
                type="number"
                label="Minimum similarity"
                value={draft.minSimilarity}
                onChange={e => set({ minSimilarity: e.target.value })}
                helperText="From 0 to 1"
              />
            </>
          )}
        </Box>
      )}

      {draft.ruleClass === RULE_CLASSES.TOOL_CALLS && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <FormControl sx={{ flex: 2, minWidth: theme => theme.spacing(30) }}>
            <InputLabel id={`${id}-trajectory`}>Match</InputLabel>
            <Select
              labelId={`${id}-trajectory`}
              label="Match"
              value={draft.trajectoryMatch}
              onChange={e => set({ trajectoryMatch: e.target.value })}
            >
              {Object.entries(TRAJECTORY_MATCH_LABELS).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl sx={{ flex: 1, minWidth: theme => theme.spacing(20) }}>
            <InputLabel id={`${id}-arguments`}>Arguments</InputLabel>
            <Select
              labelId={`${id}-arguments`}
              label="Arguments"
              value={draft.arguments}
              onChange={e => set({ arguments: e.target.value })}
            >
              {Object.entries(ARGUMENT_MATCH_LABELS).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

      <Typography
        variant="body2"
        color={error ? 'error' : 'text.secondary'}
        role={error ? 'alert' : undefined}
      >
        {error ?? `Passes when ${describeRule(draft)}.`}
      </Typography>
    </Box>
  );
}

/** A rule's settings, read-only, for review screens. */
export function RuleSummary({ draft }: { draft: RuleDraft }) {
  return (
    <Typography
      sx={theme => ({
        fontFamily: theme.typography.fontFamilyCode,
        wordBreak: 'break-word',
      })}
    >
      {describeRule(draft)}
    </Typography>
  );
}
