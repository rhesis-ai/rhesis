'use client';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import {
  noop,
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { BORDER_RADIUS } from '@/styles/theme';
import ActivityLogViewer from './components/ActivityLogViewer';
import JobField from './components/JobField';

const JOB_FIELDS = [
  'Status',
  'Type',
  'Started by',
  'Queued',
  'Started',
  'Finished',
  'Attempt',
];

/** The job page with the job's values and its log pending. The Cancel
 *  button shows only for a cancellable job, so it has no placeholder. */
export default function JobDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.jobs)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Paper
            variant="outlined"
            sx={{ p: 2, borderRadius: BORDER_RADIUS.md }}
          >
            <Grid container spacing={2}>
              {JOB_FIELDS.map(label => (
                <Grid key={label} size={{ xs: 6, sm: 3 }}>
                  <JobField
                    label={label}
                    value={
                      <TextPlaceholder>
                        {PLACEHOLDER_TEXT.crumb}
                      </TextPlaceholder>
                    }
                  />
                </Grid>
              ))}
            </Grid>
          </Paper>
          <ActivityLogViewer
            entries={[]}
            live={false}
            follow={false}
            onFollowChange={noop}
            onCopy={noop}
          />
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
