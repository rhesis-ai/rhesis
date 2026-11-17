'use client';

import * as React from 'react';
import { Button, Grid, MenuItem, Stack, TextField } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesomeOutlined';
import EditableSectionCard from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatPassRate } from '@/components/reports/ReportSection';
import { SECTION_GRID } from '@/styles/theme-constants';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ReportDetail,
  ReportRecommendation,
} from '@/utils/api-client/interfaces/report';

export const RECOMMENDATION_LABELS: Record<ReportRecommendation, string> = {
  ready: 'Ready to ship',
  ready_with_risks: 'Ready to ship, with known risks',
  not_ready: 'Not ready to ship',
};

interface SummaryDraft {
  summary: string;
  recommendation: ReportRecommendation | '';
}

function KeyNumbers({ report }: { report: ReportDetail }) {
  const metrics = report.metrics;
  if (!metrics) return null;
  const { totals } = metrics;
  const items = [
    { label: 'Pass rate', value: formatPassRate(totals.pass_rate) },
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
      : [{ label: 'Inconsistent tests', value: String(totals.inconsistent) }]),
  ];
  return (
    <Grid container {...SECTION_GRID}>
      {items.map(item => (
        <Grid
          key={item.label}
          size={{ xs: 12, sm: 6, md: items.length > 4 ? 2.4 : 3 }}
        >
          <ViewField label={item.label} value={item.value} />
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
    }),
    [report.summary, report.recommendation]
  );

  const save = async (draft: SummaryDraft) => {
    try {
      await new ApiClientFactory().getReportsClient().updateReport(report.id, {
        summary: draft.summary.trim() || null,
        recommendation: draft.recommendation || null,
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
          {isEditing ? (
            <>
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
                {Object.entries(RECOMMENDATION_LABELS).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </TextField>
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
                      setDraft({
                        summary: ai.summary,
                        recommendation: ai.recommendation,
                      });
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
            <>
              <ViewField
                label="Recommendation"
                value={
                  report.recommendation
                    ? RECOMMENDATION_LABELS[report.recommendation]
                    : undefined
                }
              />
              <ViewField
                label="Management summary"
                value={report.summary || undefined}
                multiline
              />
            </>
          )}
        </Stack>
      )}
    </EditableSectionCard>
  );
}
