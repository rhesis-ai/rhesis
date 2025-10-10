'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Chip,
  Stack,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface OverruleJudgementDrawerProps {
  open: boolean;
  onClose: () => void;
  test: TestResultDetail | null;
  currentUserName: string;
  onSave: (testId: string, overruleData: OverruleData) => void;
}

export interface OverruleData {
  originalStatus: 'passed' | 'failed';
  newStatus: 'passed' | 'failed';
  reason: string;
  overruledBy: string;
  overruledAt: string;
}

export default function OverruleJudgementDrawer({
  open,
  onClose,
  test,
  currentUserName,
  onSave,
}: OverruleJudgementDrawerProps) {
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  // Calculate original test status
  const getOriginalStatus = (): 'passed' | 'failed' => {
    if (!test) return 'failed';
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return totalMetrics > 0 && passedMetrics === totalMetrics ? 'passed' : 'failed';
  };

  const originalStatus = getOriginalStatus();

  // Reset form when drawer opens or test changes
  useEffect(() => {
    if (open && test) {
      const original = getOriginalStatus();
      // Default to opposite of original status
      setNewStatus(original === 'passed' ? 'failed' : 'passed');
      setReason('');
      setError('');
    }
  }, [open, test]);

  const handleStatusChange = (
    _event: React.MouseEvent<HTMLElement>,
    value: 'passed' | 'failed' | null
  ) => {
    if (value !== null) {
      setNewStatus(value);
      setError('');
    }
  };

  const handleSave = () => {
    // Validation
    if (!reason.trim()) {
      setError('Please provide a reason for overruling the judgement.');
      return;
    }

    if (reason.trim().length < 10) {
      setError('Reason must be at least 10 characters long.');
      return;
    }

    if (newStatus === originalStatus) {
      setError('New status must be different from the original status.');
      return;
    }

    if (!test) return;

    // Create overrule data
    const overruleData: OverruleData = {
      originalStatus,
      newStatus,
      reason: reason.trim(),
      overruledBy: currentUserName,
      overruledAt: new Date().toISOString(),
    };

    onSave(test.id, overruleData);
    onClose();
  };

  const handleCancel = () => {
    setReason('');
    setError('');
    onClose();
  };

  if (!test) return null;

  const metrics = test.test_metrics?.metrics || {};
  const metricValues = Object.values(metrics);
  const totalMetrics = metricValues.length;
  const passedMetrics = metricValues.filter(m => m.is_successful).length;

  return (
    <BaseDrawer
      open={open}
      onClose={handleCancel}
      title="Overrule Test Judgement"
      onSave={handleSave}
      saveButtonText="Overrule Judgement"
      error={error}
      width={600}
    >
      <Stack spacing={3}>
        {/* Info Alert */}
        <Alert 
          severity="warning"
          sx={{
            bgcolor: theme => `${theme.palette.warning.main}0A`,
            border: 1,
            borderColor: 'warning.light',
          }}
        >
          <Typography variant="body2">
            You are about to overrule the automated test judgement. This action will
            be recorded and attributed to you.
          </Typography>
        </Alert>

        {/* Original Status Section */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Original Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            {originalStatus === 'passed' ? (
              <>
                <CheckCircleOutlineIcon sx={{ color: 'success.main', fontSize: 20 }} />
                <Chip label="Passed" color="success" size="small" />
              </>
            ) : (
              <>
                <CancelOutlinedIcon sx={{ color: 'error.main', fontSize: 20 }} />
                <Chip label="Failed" color="error" size="small" />
              </>
            )}
            <Typography variant="body2" color="text.secondary">
              {passedMetrics}/{totalMetrics} metrics passed
            </Typography>
          </Box>
        </Box>

        {/* New Status Selection */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            New Status *
          </Typography>
          <ToggleButtonGroup
            value={newStatus}
            exclusive
            onChange={handleStatusChange}
            aria-label="test status"
            fullWidth
            sx={{ mt: 1 }}
          >
            <ToggleButton
              value="passed"
              aria-label="passed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'success.main',
                  color: 'success.contrastText',
                  '&:hover': {
                    backgroundColor: 'success.dark',
                  },
                },
              }}
            >
              <CheckCircleOutlineIcon sx={{ mr: 1, fontSize: 20 }} />
              Pass
            </ToggleButton>
            <ToggleButton
              value="failed"
              aria-label="failed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'error.main',
                  color: 'error.contrastText',
                  '&:hover': {
                    backgroundColor: 'error.dark',
                  },
                },
              }}
            >
              <CancelOutlinedIcon sx={{ mr: 1, fontSize: 20 }} />
              Fail
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Reason Field */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Reason for Overrule *
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            placeholder="Explain why you are overruling the automated judgement..."
            value={reason}
            onChange={e => {
              setReason(e.target.value);
              setError('');
            }}
            helperText={`${reason.length} characters (minimum 10 required)`}
            sx={{ mt: 1 }}
          />
        </Box>

        {/* Attribution Info */}
        <Box
          sx={{
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Attribution
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
            Overruled by: <strong>{currentUserName}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Date: <strong>{new Date().toLocaleString()}</strong>
          </Typography>
        </Box>

        {/* Note about mock */}
        <Box
          sx={{
            p: 1.5,
            bgcolor: 'action.hover',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" color="text.secondary" fontStyle="italic">
            Note: This is currently a mock implementation. Backend integration is
            pending.
          </Typography>
        </Box>
      </Stack>
    </BaseDrawer>
  );
}

