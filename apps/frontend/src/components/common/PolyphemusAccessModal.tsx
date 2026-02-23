import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  CircularProgress,
  Slider,
  Alert,
  Stack,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import Image from 'next/image';
import { useNotifications } from './NotificationContext';
import { Organization } from '@/utils/api-client/interfaces/organization';

interface PolyphemusAccessModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  userEmail: string;
  organization?: Organization;
}

const SLIDER_MARKS = [
  { value: 0, label: '0' },
  { value: 1000, label: '1k' },
  { value: 5000, label: '5k' },
  { value: 10000, label: '10k' },
];

export default function PolyphemusAccessModal({
  open,
  onClose,
  onSuccess,
  userEmail,
  organization,
}: PolyphemusAccessModalProps) {
  const [justification, setJustification] = useState('');
  const [expectedMonthlyRequests, setExpectedMonthlyRequests] = useState(1000);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { show } = useNotifications();

  const handleSubmit = async () => {
    if (!justification.trim() || justification.trim().length < 10) {
      show('Please provide a detailed justification (at least 10 characters)', {
        severity: 'error',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('/api/users/request-polyphemus-access', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          justification,
          expected_monthly_requests: expectedMonthlyRequests,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        show(
          data.message ||
            "Access request submitted successfully. We'll review it shortly.",
          { severity: 'success' }
        );
        setJustification('');
        setExpectedMonthlyRequests(1000);
        onClose();
        if (onSuccess) {
          onSuccess();
        }
      } else {
        throw new Error(data.detail || 'Failed to submit access request');
      }
    } catch (error) {
      show(
        error instanceof Error
          ? error.message
          : 'Failed to submit access request',
        {
          severity: 'error',
        }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: theme => theme.spacing(1),
        }}
      >
        <Image
          src="/logos/polyphemus-logo-favicon-transparent.svg"
          alt="Polyphemus"
          width={32}
          height={32}
        />
        <Box sx={{ fontWeight: theme => theme.typography.fontWeightBold }}>
          Request Polyphemus Access
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Alert severity="warning" sx={{ mb: theme => theme.spacing(3) }}>
          <Typography variant="body2" gutterBottom>
            <strong>Important Notice:</strong> Polyphemus is an adversarial
            model designed to generate potentially harmful content for testing
            purposes. Access is restricted to verified users belonging to
            organizations to ensure responsible use. Your request will be
            reviewed by our team.
          </Typography>
        </Alert>

        <Box sx={{ mb: theme => theme.spacing(3) }}>
          <Typography
            variant="h6"
            gutterBottom
            sx={{
              fontSize: theme => theme.typography.body1.fontSize,
              fontWeight: theme => theme.typography.fontWeightMedium,
              mb: theme => theme.spacing(2),
            }}
          >
            Request Information
          </Typography>

          <Stack spacing={1}>
            <Typography variant="body2">
              <Box component="span" sx={{ color: 'text.secondary' }}>
                Your Email:
              </Box>{' '}
              {userEmail}
            </Typography>

            {organization && (
              <>
                <Typography variant="body2">
                  <Box component="span" sx={{ color: 'text.secondary' }}>
                    Organization:
                  </Box>{' '}
                  {organization.display_name || organization.name}
                </Typography>

                {organization.website && (
                  <Typography variant="body2">
                    <Box component="span" sx={{ color: 'text.secondary' }}>
                      Website:
                    </Box>{' '}
                    {organization.website}
                  </Typography>
                )}
              </>
            )}
          </Stack>
        </Box>

        <Box sx={{ mb: theme => theme.spacing(3) }}>
          <Typography
            variant="h6"
            gutterBottom
            sx={{
              fontSize: theme => theme.typography.body1.fontSize,
              fontWeight: theme => theme.typography.fontWeightMedium,
              mb: theme => theme.spacing(0.5),
            }}
          >
            Expected Monthly Requests
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: theme => theme.spacing(1.5) }}
          >
            Estimate how many requests you expect to make per month
          </Typography>
          <Box
            sx={{
              px: theme => theme.spacing(2),
              pt: theme => theme.spacing(2),
            }}
          >
            <Slider
              value={expectedMonthlyRequests}
              onChange={(_, newValue) =>
                setExpectedMonthlyRequests(newValue as number)
              }
              min={0}
              max={10000}
              step={100}
              marks={SLIDER_MARKS}
              valueLabelDisplay="on"
              valueLabelFormat={value => {
                if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
                return value.toString();
              }}
            />
          </Box>
          <Typography
            variant="body2"
            color="primary"
            sx={{ mt: theme => theme.spacing(1), textAlign: 'center' }}
          >
            {expectedMonthlyRequests.toLocaleString()} requests/month
          </Typography>
        </Box>

        <Box>
          <Typography
            variant="h6"
            gutterBottom
            sx={{
              fontSize: theme => theme.typography.body1.fontSize,
              fontWeight: theme => theme.typography.fontWeightMedium,
              mb: theme => theme.spacing(0.5),
            }}
          >
            Justification & Use Case
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: theme => theme.spacing(1.5) }}
          >
            Please provide details about why you need access and how you'll use
            it responsibly
          </Typography>
          <TextField
            autoFocus
            margin="none"
            id="justification"
            fullWidth
            multiline
            rows={6}
            value={justification}
            onChange={e => setJustification(e.target.value)}
            required
            placeholder="Please describe:
• Why you need access to Polyphemus
• How you plan to use it (e.g., adversarial testing, red-teaming)
• The types of tests you'll be conducting
• How you'll ensure responsible use"
            helperText={`${justification.length}/2000 characters (minimum 10 required)`}
            inputProps={{
              maxLength: 2000,
            }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="primary"
          disabled={isSubmitting || justification.trim().length < 10}
          startIcon={isSubmitting ? <CircularProgress size={20} /> : null}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Request'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
