'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  TextField,
  Typography,
  Box,
  Slider,
  Alert,
  Stack,
} from '@mui/material';
import Image from 'next/image';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';
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
  const [valueLabelVisible, setValueLabelVisible] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hideValueLabelTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const { show } = useNotifications();

  const scheduleHideValueLabel = useCallback(() => {
    if (hideValueLabelTimeoutRef.current) {
      clearTimeout(hideValueLabelTimeoutRef.current);
    }
    hideValueLabelTimeoutRef.current = setTimeout(() => {
      setValueLabelVisible(false);
    }, 3000);
  }, []);

  const handleSliderChange = (_: Event, newValue: number | number[]) => {
    setExpectedMonthlyRequests(newValue as number);
    setValueLabelVisible(true);
    scheduleHideValueLabel();
  };

  useEffect(() => {
    if (!open) {
      setValueLabelVisible(false);
      if (hideValueLabelTimeoutRef.current) {
        clearTimeout(hideValueLabelTimeoutRef.current);
      }
    }
  }, [open]);

  useEffect(
    () => () => {
      if (hideValueLabelTimeoutRef.current) {
        clearTimeout(hideValueLabelTimeoutRef.current);
      }
    },
    []
  );

  const handleClose = () => {
    if (isSubmitting) return;
    onClose();
  };

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
        onSuccess?.();
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
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Request Polyphemus Access"
      titleIcon={
        <Image
          src="/logos/polyphemus-logo-favicon-transparent.svg"
          alt="Polyphemus"
          width={32}
          height={32}
        />
      }
      onSave={handleSubmit}
      saveButtonText="Submit Request"
      saveDisabled={isSubmitting || justification.trim().length < 10}
      loading={isSubmitting}
      closeButtonText="Cancel"
    >
      <Alert severity="warning">
        <Typography variant="body2" gutterBottom>
          <strong>Important Notice:</strong> Polyphemus is an adversarial model
          designed to generate potentially harmful content for testing purposes.
          Access is restricted to verified users belonging to organizations to
          ensure responsible use. Your request will be reviewed by our team.
        </Typography>
      </Alert>

      <Box sx={drawerFieldsSx}>
        <Box>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 600,
              mb: 2,
              color: theme => theme.palette.greyscale.title,
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

        <Box>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 600,
              mb: 0.5,
              color: theme => theme.palette.greyscale.title,
            }}
          >
            Expected Monthly Requests
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 1.5 }}
          >
            Estimate how many requests you expect to make per month
          </Typography>
          <Box sx={{ px: 2, pt: valueLabelVisible ? 3 : 1.5 }}>
            <Slider
              value={expectedMonthlyRequests}
              onChange={handleSliderChange}
              min={0}
              max={10000}
              step={100}
              marks={SLIDER_MARKS}
              valueLabelDisplay={valueLabelVisible ? 'on' : 'off'}
              valueLabelFormat={value => {
                if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
                return value.toString();
              }}
            />
          </Box>
          <Typography
            variant="body2"
            color="primary"
            sx={{ mt: 1, textAlign: 'center' }}
          >
            {expectedMonthlyRequests.toLocaleString()} requests/month
          </Typography>
        </Box>

        <Box>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 600,
              mb: 0.5,
              color: theme => theme.palette.greyscale.title,
            }}
          >
            Justification & Use Case
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 1.5 }}
          >
            Please provide details about why you need access and how you&apos;ll
            use it responsibly
          </Typography>
          <TextField
            autoFocus
            id="justification"
            fullWidth
            multiline
            rows={6}
            value={justification}
            onChange={e => setJustification(e.target.value)}
            required
            label="Justification"
            placeholder={`Please describe:
• Why you need access to Polyphemus
• How you plan to use it (e.g., adversarial testing, red-teaming)
• The types of tests you'll be conducting
• How you'll ensure responsible use`}
            helperText={`${justification.length}/2000 characters (minimum 10 required)`}
            inputProps={{
              maxLength: 2000,
            }}
            sx={drawerOutlinedFieldSx}
          />
        </Box>
      </Box>
    </BaseDrawer>
  );
}
