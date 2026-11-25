'use client';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import Stepper from '@mui/material/Stepper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useSearchParams } from 'next/navigation';
import { PageLayout } from '@/components/layout/PageLayout';
import { SkeletonMode, SkeletonSlot } from '@/components/loading/SkeletonMode';
import {
  directoryCrumb,
  NEW_METRIC_CRUMB,
  PAGE_HEADERS,
} from '@/constants/page-headers';
import {
  NEW_METRIC_STEPS,
  newMetricTitle,
} from './components/new-metric-header';

/** The form's first step: its section headings and fields. */
const SECTIONS = [
  { heading: 'General Information', fields: ['Name', 'Description', 'Tags'] },
  { heading: 'Evaluation Process', fields: ['Evaluation Model'] },
];

// Without this file the fallback is metrics/loading.tsx, the directory
// skeleton, the wrong shape for a form. The header, trail and stepper are
// known from the URL, so they are real; the fields wait for the models.
export default function NewMetricLoading() {
  const title = newMetricTitle(useSearchParams().get('type'));
  return (
    <SkeletonMode>
      <PageLayout
        title={title}
        breadcrumbs={[
          directoryCrumb(PAGE_HEADERS.metrics),
          { label: NEW_METRIC_CRUMB },
        ]}
      >
        <Box sx={{ width: '100%' }}>
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 4, mt: 4 }}>
            <Box sx={{ maxWidth: theme => theme.spacing(75), width: '100%' }}>
              <Stepper activeStep={0}>
                {NEW_METRIC_STEPS.map(label => (
                  <Step key={label}>
                    <StepLabel>{label}</StepLabel>
                  </Step>
                ))}
              </Stepper>
            </Box>
          </Box>
          <Paper sx={{ p: 4 }}>
            {SECTIONS.map(({ heading, fields }) => (
              <Box key={heading} sx={{ mb: 5 }}>
                <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
                  {heading}
                </Typography>
                {fields.map(label => (
                  <Box key={label} sx={{ mb: 3 }}>
                    <SkeletonSlot>
                      <TextField fullWidth label={label} />
                    </SkeletonSlot>
                  </Box>
                ))}
              </Box>
            ))}
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 2,
                mt: 4,
              }}
            >
              <SkeletonSlot>
                <Button startIcon={<ArrowBackIcon />}>Cancel</Button>
              </SkeletonSlot>
              <SkeletonSlot>
                <Button variant="contained">Next</Button>
              </SkeletonSlot>
            </Box>
          </Paper>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
