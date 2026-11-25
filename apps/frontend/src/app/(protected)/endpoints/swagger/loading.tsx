'use client';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { PageLayout } from '@/components/layout/PageLayout';
import { SkeletonMode, SkeletonSlot } from '@/components/loading/SkeletonMode';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';

const TITLE = 'Import Swagger Endpoint';

/** SwaggerEndpointForm's sections and their fields. */
const SECTIONS = [
  { heading: 'General Information', fields: ['Name', 'Description'] },
  { heading: 'Swagger Configuration', fields: ['Swagger Documentation URL'] },
  { heading: 'Project', fields: ['Project'] },
  { heading: 'Environment', fields: ['Environment'] },
];

/** The import page's header for real; the form's controls as placeholders
 *  until the form (which loads the projects list) arrives. */
export default function SwaggerImportLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        title={TITLE}
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.endpoints), { label: TITLE }]}
      >
        <Card>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 2 }}>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <SkeletonSlot>
                <Button variant="outlined">Cancel</Button>
              </SkeletonSlot>
              <SkeletonSlot>
                <Button variant="contained">Create Endpoint</Button>
              </SkeletonSlot>
            </Box>
          </Box>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              {SECTIONS.map(({ heading, fields }) => (
                <Grid key={heading} size={12}>
                  <Typography variant="subtitle1" sx={{ mb: 2 }}>
                    {heading}
                  </Typography>
                  <Grid container spacing={2}>
                    {fields.map(label => (
                      <Grid
                        key={label}
                        size={{ xs: 12, md: fields.length > 1 ? 6 : 12 }}
                      >
                        <SkeletonSlot>
                          <TextField fullWidth label={label} />
                        </SkeletonSlot>
                      </Grid>
                    ))}
                  </Grid>
                </Grid>
              ))}
            </Grid>
          </Box>
        </Card>
      </PageLayout>
    </SkeletonMode>
  );
}
