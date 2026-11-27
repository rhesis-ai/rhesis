'use client';

import * as React from 'react';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import InputAdornment from '@mui/material/InputAdornment';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useMetricTargetOptions } from '@/hooks/useLookups';
import {
  TARGET_PREVIEW_TRACES,
  useMetricTargetPreview,
  useSpanAttributeCatalogue,
} from '@/hooks/useMetricTargetBuilder';
import { readActiveProjectId } from '@/utils/active-project';
import type {
  ConditionOperatorChoice,
  MetricTarget,
  MetricTargetAggregate,
  MetricTargetChoice,
  ReaderChoice,
  SpecialFieldChoice,
} from '@/utils/api-client/interfaces/metric';
import {
  defaultOperator,
  draftProblem,
  emptyCondition,
  fieldOptions as buildFieldOptions,
  isPerSpanTarget,
  isPerUnitTarget,
  readKeySuggestions,
  shareProblem,
  switchTarget,
  TARGET_AGGREGATE,
  targetFromDraft,
  targetKey,
  type TargetDraft,
  valueSuggestions,
} from '@/utils/metric-target-draft';
import { METRIC_TARGET, targetSpanKind } from '@/utils/metric-targets';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import TargetChoiceRadios from './TargetChoiceRadios';
import TargetConditionRow from './TargetConditionRow';
import TargetPreviewPanel from './TargetPreviewPanel';
import TargetSummaryText from './TargetSummaryText';

interface MetricTargetBuilderProps {
  /** The targets to offer, "Custom spans" included when the metric takes it. */
  choices: MetricTargetChoice[];
  value: TargetDraft;
  onChange: (draft: TargetDraft) => void;
  /** The stored target and its summary, shown while the draft still equals it. */
  savedTarget?: MetricTarget | null;
  savedSummary?: string | null;
  /** Mark incomplete conditions (after a save attempt). */
  showErrors?: boolean;
  /** Told the summary of the draft as the API words it, once known. */
  onSummaryChange?: (summary: string | null) => void;
}

const PASS_RULE_LABELS: Record<MetricTargetAggregate, string> = {
  [TARGET_AGGREGATE.ALL]: 'all',
  [TARGET_AGGREGATE.ANY]: 'at least one',
  [TARGET_AGGREGATE.SHARE]: 'at least',
};

const NO_STRINGS: string[] = [];
const NO_READERS: ReaderChoice[] = [];
const NO_OPERATORS: ConditionOperatorChoice[] = [];
const NO_SPECIAL_FIELDS: SpecialFieldChoice[] = [];

function SectionLabel({
  id,
  children,
}: {
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <Typography
      id={id}
      variant="overline"
      component="h3"
      color="text.secondary"
      sx={{ display: 'block', mb: 1 }}
    >
      {children}
    </Typography>
  );
}

function unitNoun(on: string, choices: MetricTargetChoice[]) {
  if (on === METRIC_TARGET.TURN) return { one: 'turn', many: 'turns' };
  if (isPerSpanTarget(on, choices)) return { one: 'span', many: 'spans' };
  return { one: 'match', many: 'matches' };
}

/** A `read` field: the API's readers, then the kind's attribute keys; any key or event can be typed. */
function ReadField({
  label,
  value,
  onChange,
  readers,
  keys,
  helperText,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  readers: ReaderChoice[];
  keys: string[];
  helperText: string;
}) {
  const options = React.useMemo(
    () => [...readers.map(r => r.reader), ...keys],
    [readers, keys]
  );
  const readerLabels = React.useMemo(
    () => new Map(readers.map(r => [r.reader, r.label])),
    [readers]
  );
  return (
    <Autocomplete
      freeSolo
      size="small"
      options={options}
      inputValue={value}
      onInputChange={(_e, text) => onChange(text)}
      renderOption={(props, option) => {
        const { key, ...rest } = props;
        return (
          <Box
            component="li"
            key={key}
            {...rest}
            sx={{ display: 'flex', gap: 2 }}
          >
            <Typography
              variant="body2"
              sx={{
                flex: 1,
                fontFamily: theme => theme.typography.fontFamilyCode,
              }}
            >
              {option}
            </Typography>
            {readerLabels.has(option) && (
              <Typography variant="caption" color="text.secondary">
                {readerLabels.get(option)}
              </Typography>
            )}
          </Box>
        );
      }}
      renderInput={params => (
        <TextField
          {...params}
          label={label}
          placeholder="Its own"
          helperText={helperText}
          sx={{
            '& input': { fontFamily: theme => theme.typography.fontFamilyCode },
          }}
        />
      )}
    />
  );
}

/**
 * The target section in build mode: start from a preset or custom spans, narrow
 * with conditions read from the project's recent spans, choose what the metric
 * reads and how the units' verdicts combine. The summary and the preview come
 * from the API, so they say exactly what evaluation will do.
 */
export default function MetricTargetBuilder({
  choices,
  value: draft,
  onChange,
  savedTarget,
  savedSummary,
  showErrors = false,
  onSummaryChange,
}: MetricTargetBuilderProps) {
  const a11yId = React.useId();
  const { activeProject } = useActiveProject();
  const projectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();
  const { data: options } = useMetricTargetOptions();
  const operators = options?.operators ?? NO_OPERATORS;
  const specialFields = options?.special_fields ?? NO_SPECIAL_FIELDS;
  const readers = options?.readers ?? NO_READERS;
  const eventPrefix = options?.event_prefix;
  const allTargets = options?.targets ?? choices;
  const { data: catalogue } = useSpanAttributeCatalogue(projectId);

  const selected = choices.find(c => c.on === draft.on);
  // The full registry, not the offered choices: a stored target no longer
  // offered keeps its fields.
  const perUnit = isPerUnitTarget(draft.on, allTargets);
  const perSpan = isPerSpanTarget(draft.on, allTargets);
  const isCustom = draft.on === METRIC_TARGET.SPAN;

  const target = React.useMemo(
    () => targetFromDraft(draft, allTargets, operators),
    [draft, allTargets, operators]
  );
  const problem = draftProblem(draft, allTargets, operators);
  const shareError = shareProblem(draft);
  const matchesSaved =
    !!savedTarget && targetKey(target) === targetKey(savedTarget);
  const preview = useMetricTargetPreview(projectId, problem ? null : target);
  const previewSummary =
    preview.data && !preview.pending && !preview.isPlaceholderData
      ? (preview.data.target_summary ?? null)
      : null;
  const summary = matchesSaved
    ? (savedSummary ?? previewSummary)
    : problem
      ? null
      : previewSummary;

  React.useEffect(() => {
    onSummaryChange?.(summary);
  }, [summary, onSummaryChange]);

  const fieldOptionList = React.useMemo(
    () => buildFieldOptions(specialFields, catalogue, allTargets),
    [specialFields, catalogue, allTargets]
  );
  const spanKind = targetSpanKind(target, allTargets);
  const readKeys = React.useMemo(
    () => readKeySuggestions(catalogue, spanKind),
    [catalogue, spanKind]
  );

  const update = (patch: Partial<TargetDraft>) =>
    onChange({ ...draft, ...patch });

  const choose = (on: string) =>
    onChange(switchTarget(draft, on, allTargets, operators));

  // After a row is removed, focus moves to the next row's remove button, else
  // the previous one's, else "Add condition", never to the page's top.
  const removeButtons = React.useRef(new Map<string, HTMLButtonElement>());
  const addButton = React.useRef<HTMLButtonElement>(null);
  const focusAfterRemove = React.useRef<string | null | undefined>(undefined);
  React.useEffect(() => {
    const next = focusAfterRemove.current;
    if (next === undefined) return;
    focusAfterRemove.current = undefined;
    const button = next ? removeButtons.current.get(next) : addButton.current;
    button?.focus();
  }, [draft.conditions]);

  const removeCondition = (index: number) => {
    const rows = draft.conditions;
    focusAfterRemove.current =
      rows[index + 1]?.id ?? rows[index - 1]?.id ?? null;
    update({ conditions: rows.filter((_c, i) => i !== index) });
  };

  const unit = unitNoun(draft.on, allTargets);
  const previewBlocked = problem
    ? 'The preview runs once the target is complete.'
    : null;
  const noSummaryText =
    problem ??
    (projectId
      ? 'The summary appears with the preview.'
      : 'The summary appears once the metric is saved.');

  return (
    <Box
      data-testid="metric-target-builder"
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 2fr) minmax(0, 1fr)' },
        gap: 3,
        alignItems: 'start',
      }}
    >
      <Box
        sx={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}
      >
        <Box>
          <SectionLabel id={`${a11yId}-start`}>Start from</SectionLabel>
          <TargetChoiceRadios
            labelledBy={`${a11yId}-start`}
            choices={choices}
            registry={allTargets}
            value={draft.on}
            onChange={choose}
          />
          {selected && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 1 }}
              data-testid="metric-target-description"
            >
              {selected.description}
            </Typography>
          )}
        </Box>

        {perSpan && (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
              gap: 2,
            }}
          >
            {!isCustom && (
              <TextField
                size="small"
                label="Name"
                value={draft.name}
                onChange={e => update({ name: e.target.value })}
                helperText="Optional. Only spans with this tool, agent or model name."
              />
            )}
            <TextField
              size="small"
              label="Inside agent"
              value={draft.within}
              onChange={e => update({ within: e.target.value })}
              helperText="Optional. Only spans under the agent with this name, at any depth."
            />
          </Box>
        )}

        {perUnit && (
          <Box>
            <SectionLabel id={`${a11yId}-where`}>
              {isCustom
                ? 'Judge each span where'
                : `Only ${unit.many} where (optional)`}
            </SectionLabel>
            <Box
              role="group"
              aria-labelledby={`${a11yId}-where`}
              sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}
            >
              {draft.conditions.map((condition, i) => (
                <TargetConditionRow
                  key={condition.id}
                  index={i + 1}
                  condition={condition}
                  operators={operators}
                  specialFields={specialFields}
                  fieldOptions={fieldOptionList}
                  suggestions={
                    condition.field
                      ? valueSuggestions(condition.field, catalogue)
                      : NO_STRINGS
                  }
                  showErrors={showErrors}
                  onChange={next =>
                    update({
                      conditions: draft.conditions.map(c =>
                        c.id === condition.id ? next : c
                      ),
                    })
                  }
                  onRemove={() => removeCondition(i)}
                  removeButtonRef={button => {
                    if (button) removeButtons.current.set(condition.id, button);
                    else removeButtons.current.delete(condition.id);
                  }}
                />
              ))}
              <Box>
                <Button
                  ref={addButton}
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() =>
                    update({
                      conditions: [
                        ...draft.conditions,
                        emptyCondition(defaultOperator(operators)),
                      ],
                    })
                  }
                  disabled={operators.length === 0}
                >
                  Add condition
                </Button>
              </Box>
            </Box>
          </Box>
        )}

        {perUnit && (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
              gap: 2,
            }}
          >
            <ReadField
              label="The metric reads as input"
              value={draft.readInput}
              onChange={readInput => update({ readInput })}
              readers={readers}
              keys={readKeys}
              helperText={`Empty: the ${unit.one}'s own input. Or an attribute key${
                eventPrefix ? `, or ${eventPrefix}<name> for an event` : ''
              }.`}
            />
            <ReadField
              label="And as output"
              value={draft.readOutput}
              onChange={readOutput => update({ readOutput })}
              readers={readers}
              keys={readKeys}
              helperText={`Empty: the ${unit.one}'s own output.`}
            />
          </Box>
        )}

        {perUnit && (
          <Box
            role="group"
            aria-label="Pass rule"
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Typography variant="body1">The metric passes when</Typography>
            <TextField
              select
              size="small"
              value={draft.aggregate}
              onChange={e =>
                update({ aggregate: e.target.value as MetricTargetAggregate })
              }
              slotProps={{
                htmlInput: { 'aria-label': 'How many must pass' },
              }}
            >
              {Object.values(TARGET_AGGREGATE).map(aggregate => (
                <MenuItem key={aggregate} value={aggregate}>
                  {PASS_RULE_LABELS[aggregate]}
                </MenuItem>
              ))}
            </TextField>
            {draft.aggregate === TARGET_AGGREGATE.SHARE && (
              <TextField
                size="small"
                value={draft.minSharePercent}
                onChange={e => update({ minSharePercent: e.target.value })}
                error={!!shareError}
                helperText={shareError ?? undefined}
                sx={{ width: theme => theme.spacing(12) }}
                slotProps={{
                  htmlInput: {
                    inputMode: 'decimal',
                    'aria-label': 'Share that must pass, in percent',
                  },
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">%</InputAdornment>
                    ),
                  },
                }}
              />
            )}
            <Typography variant="body1">
              of the matching {unit.many} pass.
            </Typography>
          </Box>
        )}

        <Box
          data-testid="target-summary"
          sx={{
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: BORDER_RADIUS.sm,
          }}
        >
          {problem && showErrors ? (
            <Typography variant="body2" color="error.main" role="alert">
              {problem}
            </Typography>
          ) : summary ? (
            <Typography variant="body2">
              Judges <TargetSummaryText summary={summary} />.
              {perUnit && ' A trace where it picks nothing is not applicable.'}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {noSummaryText}
            </Typography>
          )}
        </Box>
      </Box>

      <TargetPreviewPanel
        preview={preview.data}
        stale={preview.pending || preview.isFetching}
        loading={preview.isLoading}
        error={problem ? null : preview.error}
        blocked={previewBlocked}
        noProject={!projectId}
        traces={TARGET_PREVIEW_TRACES}
        unitNoun={unit}
      />
    </Box>
  );
}
