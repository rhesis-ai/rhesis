'use client';

import { Grid, Typography } from '@mui/material';
import { LoadingButton } from '@mui/lab';
import { PlayArrowIcon } from '@/components/icons';
import SectionCard from '@/components/common/SectionCard';
import { useEndpointDetailContext } from './EndpointDetailContext';
import JsonMonacoField from './JsonMonacoField';

export default function EndpointTestTab() {
  const {
    editorTheme,
    editorWrapperStyle,
    testInput,
    setTestInput,
    testResponse,
    isTestingEndpoint,
    runTest,
  } = useEndpointDetailContext();

  return (
    <SectionCard title="Test connection">
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Enter sample JSON. It will be matched to your request template and
        parsed using your response mappings.
      </Typography>
      <Grid container spacing={2}>
        <Grid size={12}>
          <JsonMonacoField
            editorKey="test-input"
            height="280px"
            theme={editorTheme}
            wrapperSx={editorWrapperStyle}
            value={testInput}
            onChange={setTestInput}
          />
        </Grid>
        <Grid size={12}>
          <LoadingButton
            variant="contained"
            color="primary"
            onClick={runTest}
            loading={isTestingEndpoint}
            loadingPosition="start"
            startIcon={<PlayArrowIcon />}
          >
            Test Endpoint
          </LoadingButton>
        </Grid>
        {testResponse && (
          <Grid size={12}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Response
            </Typography>
            <JsonMonacoField
              editorKey="test-response"
              height="280px"
              theme={editorTheme}
              wrapperSx={editorWrapperStyle}
              value={testResponse}
              readOnly
            />
          </Grid>
        )}
      </Grid>
    </SectionCard>
  );
}
