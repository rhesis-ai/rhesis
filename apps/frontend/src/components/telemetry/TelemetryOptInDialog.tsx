'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Link,
  Collapse,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';

interface TelemetryOptInDialogProps {
  open: boolean;
  onOptIn: () => void;
  onOptOut: () => void;
}

export default function TelemetryOptInDialog({
  open,
  onOptIn,
  onOptOut,
}: TelemetryOptInDialogProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <Dialog open={open} maxWidth="sm" fullWidth>
      <DialogTitle>Help Improve Rhesis</DialogTitle>
      
      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2}>
          <Typography>
            Would you like to help improve Rhesis by sharing anonymous usage data?
          </Typography>

          <Typography variant="body2" color="text.secondary">
            We collect anonymous usage statistics to understand how features are used
            and to improve the product. No personally identifiable information is collected.
          </Typography>

          <Button
            variant="text"
            size="small"
            onClick={() => setShowDetails(!showDetails)}
            endIcon={
              <ExpandMoreIcon
                sx={{
                  transform: showDetails ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.3s',
                }}
              />
            }
            sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
          >
            What data is collected?
          </Button>

          <Collapse in={showDetails}>
            <Box sx={{ pl: 2, borderLeft: '3px solid', borderColor: 'divider' }}>
              <Typography variant="body2" gutterBottom>
                <strong>We collect:</strong>
              </Typography>
              <Typography variant="body2" component="ul" sx={{ mt: 1, mb: 2 }}>
                <li>Feature usage statistics</li>
                <li>Page views and navigation patterns</li>
                <li>API endpoint usage</li>
                <li>Performance metrics</li>
              </Typography>

              <Typography variant="body2" gutterBottom>
                <strong>We DON'T collect:</strong>
              </Typography>
              <Typography variant="body2" component="ul" sx={{ mt: 1 }}>
                <li>Email addresses or names</li>
                <li>Test data or prompts</li>
                <li>API keys or credentials</li>
                <li>Any personally identifiable information</li>
              </Typography>
            </Box>
          </Collapse>

          <Typography variant="body2" color="text.secondary">
            <Link
              href="https://docs.rhesis.ai/privacy"
              target="_blank"
              rel="noopener noreferrer"
            >
              Learn more about our privacy practices →
            </Link>
          </Typography>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            You can change this setting at any time in your account settings.
          </Typography>
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onOptOut} color="inherit">
          No Thanks
        </Button>
        <Button onClick={onOptIn} variant="contained" color="primary">
          Yes, Help Improve Rhesis
        </Button>
      </DialogActions>
    </Dialog>
  );
}

