'use client';

import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';

interface Breadcrumb {
  label: string;
  href?: string;
}

interface DetailNotFoundStateProps {
  entityLabel: string;
  entityId: string;
  breadcrumbs: Breadcrumb[];
  onBack: () => void;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export default function DetailNotFoundState({
  entityLabel,
  entityId,
  breadcrumbs,
  onBack,
  onRetry,
  isRetrying = false,
}: DetailNotFoundStateProps) {
  const listLabel = entityLabel.endsWith('s') ? entityLabel : `${entityLabel}s`;

  return (
    <PageLayout title={`${entityLabel} Not Found`} breadcrumbs={breadcrumbs}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Sorry, we couldn&apos;t load this {entityLabel.toLowerCase()}
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            The {entityLabel.toLowerCase()} you&apos;re looking for might have
            been deleted, moved, belongs to a different project, or you may not
            have permission to view it.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {entityLabel} ID: {entityId}
          </Typography>
        </Alert>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button variant="contained" onClick={onBack}>
            Back to {listLabel}
          </Button>
          {onRetry && (
            <Button variant="outlined" onClick={onRetry} disabled={isRetrying}>
              {isRetrying ? (
                <>
                  <CircularProgress color="inherit" size={16} sx={{ mr: 1 }} />
                  Retrying...
                </>
              ) : (
                'Try Again'
              )}
            </Button>
          )}
        </Box>
      </Box>
    </PageLayout>
  );
}
