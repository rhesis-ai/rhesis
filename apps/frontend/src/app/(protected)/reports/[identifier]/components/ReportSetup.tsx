'use client';

import * as React from 'react';
import {
  Checkbox,
  FormControl,
  FormControlLabel,
  FormHelperText,
  Grid,
  MenuItem,
  TextField,
} from '@mui/material';
import EditableSectionCard from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { useNotifications } from '@/components/common/NotificationContext';
import { RESULT_RULES } from '@/components/reports/resultRules';
import { SECTION_GRID } from '@/styles/theme-constants';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ReportDetail,
  ReportResultRule,
  ReportUpdate,
} from '@/utils/api-client/interfaces/report';

interface SetupDraft {
  result_rule: ReportResultRule;
  baseline_report_id: string;
  is_release: boolean;
}

interface ReportSetupProps {
  report: ReportDetail;
  editable: boolean;
  update: (body: ReportUpdate) => Promise<void>;
  onEditingChange?: (isEditing: boolean) => void;
}

/** How the numbers are made: counting rule, comparison, release or not. Changing it
 * recomputes the whole page, so it sits apart from the summary text. */
export default function ReportSetup({
  report,
  editable,
  update,
  onEditingChange,
}: ReportSetupProps) {
  const notifications = useNotifications();
  const initialValue = React.useMemo<SetupDraft>(
    () => ({
      result_rule: report.result_rule,
      baseline_report_id: report.baseline_report_id ?? '',
      is_release: report.is_release,
    }),
    [report.result_rule, report.baseline_report_id, report.is_release]
  );
  const comparison = useComparisonChoices(report, editable);
  const baselineTitle =
    report.metrics?.comparison?.baseline.title ??
    comparison.choices.find(c => c.id === report.baseline_report_id)?.title;

  const save = async (draft: SetupDraft) => {
    try {
      await update({
        result_rule: draft.result_rule,
        baseline_report_id: draft.baseline_report_id || null,
        is_release: draft.is_release,
      });
      return true;
    } catch {
      notifications.show('Failed to save the setup', {
        severity: 'error',
        autoHideDuration: 5000,
      });
      return false;
    }
  };

  return (
    <EditableSectionCard<SetupDraft>
      title="Setup"
      subtitle="How the numbers below are counted and compared."
      editable={editable}
      initialValue={initialValue}
      onSave={save}
      onEditingChange={onEditingChange}
    >
      {({ draft, setDraft, isEditing }) => (
        <Grid container {...SECTION_GRID}>
          <Grid size={{ xs: 12, md: 4 }}>
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
          <Grid size={{ xs: 12, md: 4 }}>
            {isEditing ? (
              <TextField
                select
                label="Compared with"
                value={draft.baseline_report_id}
                onChange={e =>
                  setDraft(d => ({ ...d, baseline_report_id: e.target.value }))
                }
                helperText={
                  comparison.failed
                    ? 'Could not load published reports'
                    : comparison.loading
                      ? 'Loading published reports…'
                      : 'A published report for this endpoint, e.g. the last release or experiment'
                }
                error={comparison.failed}
                fullWidth
              >
                <MenuItem value="">No comparison</MenuItem>
                {comparison.choices.map(choice => (
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
          <Grid size={{ xs: 12, md: 4 }}>
            {isEditing ? (
              <FormControl>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={draft.is_release}
                      onChange={e =>
                        setDraft(d => ({ ...d, is_release: e.target.checked }))
                      }
                    />
                  }
                  label="This is a release report"
                />
                <FormHelperText>
                  {draft.is_release
                    ? 'It ends with a recommendation: ready to ship or not.'
                    : 'A plain report across runs. Any recommendation is removed.'}
                </FormHelperText>
              </FormControl>
            ) : (
              <ViewField
                label="Type"
                value={report.is_release ? 'Release report' : 'General report'}
                helperText={
                  report.is_release
                    ? 'Ends with a ship recommendation'
                    : 'No ship recommendation'
                }
              />
            )}
          </Grid>
        </Grid>
      )}
    </EditableSectionCard>
  );
}

interface Choice {
  id: string;
  title: string;
}

/** The endpoint's other published reports, newest first: what a draft can compare
 * with. Only loaded while the report can still change. */
function useComparisonChoices(report: ReportDetail, editable: boolean) {
  const [state, setState] = React.useState<{
    choices: Choice[];
    loading: boolean;
    failed: boolean;
  }>({ choices: [], loading: editable, failed: false });

  React.useEffect(() => {
    if (!editable) return;
    let cancelled = false;
    setState(s => ({ ...s, loading: true, failed: false }));
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
        if (!cancelled) {
          setState({
            choices: page.data
              .filter(r => r.id !== report.id)
              .map(r => ({ id: r.id, title: r.title })),
            loading: false,
            failed: false,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setState({ choices: [], loading: false, failed: true });
      });
    return () => {
      cancelled = true;
    };
  }, [editable, report.endpoint_id, report.id]);

  // Keep the current baseline selectable even when it's older than the first page.
  const current = report.metrics?.comparison?.baseline;
  const choices =
    current && !state.choices.some(c => c.id === current.id)
      ? [...state.choices, { id: current.id, title: current.title }]
      : state.choices;
  return { ...state, choices };
}
