import { PageContainer } from '@toolpad/core/PageContainer';
import { Paper, Box, Typography, Alert } from '@mui/material';
import { PsychologyIcon } from '@/components/icons';

export default function BehaviorsPage() {
  return (
    <PageContainer
      title="Behaviors"
      breadcrumbs={[{ title: 'Behaviors', path: '/behaviors' }]}
    >
      <Paper sx={{ p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            py: 4,
          }}
        >
          <PsychologyIcon sx={{ fontSize: 64, color: 'primary.main' }} />
          <Typography variant="h5" component="h2" gutterBottom>
            Behaviors
          </Typography>
          <Alert severity="info" sx={{ maxWidth: 600 }}>
            This feature is coming soon. Behaviors will allow you to define and
            manage expected behavior patterns for your AI agents.
          </Alert>
        </Box>
      </Paper>
    </PageContainer>
  );
}
