'use client';

import * as React from 'react';
import {
  Button,
  Checkbox,
  FormControlLabel,
  Grid,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesomeOutlined';
import EditableSectionCard from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { useNotifications } from '@/components/common/NotificationContext';
import {
  formatDelta,
  formatPassRate,
} from '@/components/reports/ReportSection';
import { SECTION_GRID } from '@/styles/theme-constants';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  Report,
  ReportDetail,
  ReportRecommendation,
  ReportResultRule,
} from '@/utils/api-client/interfaces/report';
import { RESULT_RULES } from '@/components/reports/resultRules';
import BeforeYouDecide from './BeforeYouDecide';

export const RECOMMENDATION_LABELS: Record<ReportRecommendation, string> = {
  ready: 'Ready to ship',
  ready_with_risks: 'Ready to ship, with known risks',
  not_ready: 'Not ready to ship',
};

interface SummaryDraft {
  summary: string;
  recommendation: ReportRecommendation | '';
  result_rule: ReportResultRule;
  baseline_report_id: string;
  is_release: boolean;
}

function KeyNumbers({ report }: { report: ReportDetail }) {
  const metrics = report.metrics;
  if (!metrics) return null;
  const { totals } = metrics;
  const delta = metrics.comparison?.pass_rate_delta;
  const items = [
    {
      label: 'Pass rate',
      value: formatPassRate(totals.pass_rate),
      helper:
        delta === null || delta === undefined
          ? undefined
          : `${formatDelta(delta)} pts vs ${metrics.comparison?.baseline.title}`,
    },
    {
      label: 'Results',
      value: totals.errored
        ? `${totals.results} (${totals.errored} errored)`
        : String(totals.results),
    },
    { label: 'Runs', value: String(metrics.runs.length) },
    {
      label: 'Requirements tested',
      value: `${totals.requirements_tested} of ${totals.requirements_total}`,
    },
    ...(metrics.result_rule === 'latest'
      ? []
      : [
          {
            label: 'Tests with mixed results',
            value: String(totals.inconsistent),
          },
        ]),
  ];
  return (
    <Grid container {...SECTION_GRID}>
      {items.map(item => (
        <Grid
          key={item.label}
          size={{ xs: 12, sm: 6, md: items.length > 4 ? 2.4 : 3 }}
        >
          <ViewField
            label={item.label}
            value={item.value}
            helperText={'helper' in item ? item.helper : undefined}
          />
        </Grid>
      ))}
    </Grid>
  );
}

interface ReportSummaryProps {
  report: ReportDetail;
  editable: boolean;
  onSaved: () => Promise<void>;
}

export default function ReportSummary({
  report,
  editable,
  onSaved,
}: ReportSummaryProps) {
  const notifications = useNotifications();
  const [drafting, setDrafting] = React.useState(false);
  const initialValue = React.useMemo<SummaryDraft>(
    () => ({
      summary: report.summary ?? '',
      recommendation: report.recommendation ?? '',
      result_rule: report.result_rule,
      baseline_report_id: report.baseline_report_id ?? '',
      is_release: report.is_release,
    }),
    [
      report.summary,
      report.recommendation,
      report.result_rule,
      report.baseline_report_id,
      report.is_release,
    ]
  );

  const save = async (draft: SummaryDraft) => {
    try {
      await new ApiClientFactory().getReportsClient().updateReport(report.id, {
        summary: draft.summary.trim() || null,
        recommendation: (draft.is_release && draft.recommendation) || null,
        is_release: draft.is_release,
        result_rule: draft.result_rule,
        baseline_report_id: draft.baseline_report_id || null,
      });
      await onSaved();
      return true;
    } catch {
      notifications.show('Failed to save the summary', {
        severity: 'error',
        autoHideDuration: 5000,
      });
      return false;
    }
  };

  const choices = useComparisonChoices(report);
  const baselineTitle =
    report.metrics?.comparison?.baseline.title ??
    choices.find(c => c.id === report.baseline_report_id)?.title;

  return (
    <EditableSectionCard<SummaryDraft>
      title="Summary"
      editable={editable}
      initialValue={initialValue}
      onSave={save}
    >
      {({ draft, setDraft, isEditing }) => (
        <Stack spacing={3}>
          <KeyNumbers report={report} />
          <BeforeYouDecide
            metrics={report.metrics}
            isRelease={report.is_release}
          />
          {isEditing && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={draft.is_release}
                  onChange={e =>
                    setDraft(d => ({ ...d, is_release: e.target.checked }))
                  }
                />
              }
              label="This is a release report, with a ship recommendation"
            />
          )}
          <Grid container {...SECTION_GRID}>
            {(isEditing ? draft.is_release : report.is_release) && (
              <Grid size={{ xs: 12, md: 4 }}>
                {isEditing ? (
                  <TextField
                    select
                    label="Recommendation"
                    value={draft.recommendation}
                    onChange={e =>
                      setDraft(d => ({
                        ...d,
                        recommendation: e.target
                          .value as SummaryDraft['recommendation'],
                      }))
                    }
                    fullWidth
                  >
                    <MenuItem value="">Not set</MenuItem>
                    {Object.entries(RECOMMENDATION_LABELS).map(
                      ([value, label]) => (
                        <MenuItem key={value} value={value}>
                          {label}
                        </MenuItem>
                      )
                    )}
                  </TextField>
                ) : (
                  <ViewField
                    label="Recommendation"
                    value={
                      report.recommendation
                        ? RECOMMENDATION_LABELS[report.recommendation]
                        : undefined
                    }
                  />
                )}
              </Grid>
            )}
            <Grid size={{ xs: 12, md: 'grow' }}>
              {isEditing ? (
                <TextField
                  select
                  label="Counting"
                  value={draft.result_rule}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      result_rule: e.target.value as ReportResultRule,
                    }))
                  }
                  helperText={RESULT_RULES[draft.result_rule].description}
                  fullWidth
                >
                  {Object.entries(RESULT_RULES).map(([value, { label }]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
              ) : (
                <ViewField
                  label="Counting"
                  value={RESULT_RULES[report.result_rule].label}
                  helperText={RESULT_RULES[report.result_rule].description}
                />
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 'grow' }}>
              {isEditing ? (
                <TextField
                  select
                  label="Compared with"
                  value={draft.baseline_report_id}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      baseline_report_id: e.target.value,
                    }))
                  }
                  helperText="A published report for this endpoint, e.g. the last release or experiment"
                  fullWidth
                >
                  <MenuItem value="">No comparison</MenuItem>
                  {choices.map(choice => (
                    <MenuItem key={choice.id} value={choice.id}>
                      {choice.title}
                    </MenuItem>
                  ))}
                </TextField>
              ) : (
                <ViewField
                  label="Compared with"
                  value={baselineTitle ?? 'No comparison'}
                />
              )}
            </Grid>
          </Grid>
          {isEditing ? (
            <>
              <TextField
                multiline
                minRows={4}
                label="Management summary"
                placeholder="What was tested, how it went, what failed and what happens next."
                helperText="Draft with AI uses only this report's numbers. Read it and edit it before you save."
                value={draft.summary}
                onChange={e =>
                  setDraft(d => ({ ...d, summary: e.target.value }))
                }
                inputProps={{ maxLength: 2000 }}
                fullWidth
              />
              <Stack direction="row">
                <Button
                  variant="outlined"
                  startIcon={<AutoAwesomeIcon />}
                  disabled={drafting}
                  sx={sectionEditButtonSx}
                  onClick={async () => {
                    setDrafting(true);
                    try {
                      const ai = await new ApiClientFactory()
                        .getReportsClient()
                        .draftSummary(report.id);
                      setDraft(d => ({
                        ...d,
                        summary: ai.summary,
                        recommendation: ai.recommendation ?? '',
                      }));
                    } catch {
                      notifications.show(
                        'Could not draft the summary. Check your generation model.',
                        { severity: 'error', autoHideDuration: 5000 }
                      );
                    } finally {
                      setDrafting(false);
                    }
                  }}
                >
                  Draft with AI
                </Button>
              </Stack>
            </>
          ) : (
            <ViewField
              label="Management summary"
              value={report.summary || undefined}
              multiline
            />
          )}
        </Stack>
      )}
    </EditableSectionCard>
  );
}

/** The endpoint's other published reports, newest first: what a report can compare with. */
function useComparisonChoices(report: ReportDetail): Report[] {
  const [choices, setChoices] = React.useState<Report[]>([]);
  React.useEffect(() => {
    let cancelled = false;
    new ApiClientFactory()
      .getReportsClient()
      .getReportsPage({
        skip: 0,
        limit: 100,
        sort_by: 'published_at',
        sort_order: 'desc',
        $filter: `endpoint_id eq '${report.endpoint_id}' and status eq 'published'`,
      })
      .then(page => {
        if (!cancelled) setChoices(page.data.filter(r => r.id !== report.id));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [report.endpoint_id, report.id]);
  return choices;
}
