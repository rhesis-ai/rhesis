'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';
import CheckIcon from '@mui/icons-material/Check';
import HistoryIcon from '@mui/icons-material/History';
import { SectionCard } from '@/components/common/SectionCard';
import { usePlan } from '@/contexts/FeaturesContext';
import { UPGRADE_URL } from '@/constants/quota';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { resolvePlanStyle, type PlanVariant } from '@/utils/plan';

const LAPSED: PlanVariant = 'lapsed';

const BENEFITS = [
  'Before and after values for every change, from the web app, SDK, API, MCP and the Architect',
  'Append-only: nobody can edit or delete entries',
  'An Auditor role that reads everything and changes nothing',
  'Export to JSON Lines or CSV, and stream events to Splunk, Datadog or a webhook within seconds',
  'Ask the Architect who changed a metric or why a test run regressed',
  'Works with SSO and custom roles',
] as const;

function openPricing() {
  window.open(UPGRADE_URL, '_blank', 'noopener,noreferrer');
}

/**
 * The `FeatureGate` fallback for the audit log. `/features` leaves
 * `audit_log` out both without a licence and with a lapsed one; the plan's
 * `is_paid`/`is_active` pair tells the two apart.
 */
export default function AuditLogTeaser() {
  const lapsed = resolvePlanStyle(usePlan()).variant === LAPSED;

  return (
    <SectionCard>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2.5,
          maxWidth: theme => theme.spacing(80),
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: theme => theme.spacing(6),
            height: theme => theme.spacing(6),
            borderRadius: BORDER_RADIUS.md,
            bgcolor: theme => alpha(theme.palette.primary.main, 0.1),
            color: 'primary.main',
          }}
        >
          <HistoryIcon />
        </Box>

        {lapsed ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="h6">
              The audit log needs an active Enterprise licence
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Your licence is no longer active, so new changes are not recorded
              and the log cannot be opened. Entries recorded before are kept
              until your retention period removes them, and are back in view
              once you renew.
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="h6">See who changed what, and when</Typography>
            <Typography variant="body2" color="text.secondary">
              The audit log is part of Rhesis Enterprise. It records changes to
              access, tests, metrics and endpoint configuration, so you can
              answer auditors with evidence instead of screenshots.
            </Typography>
          </Box>
        )}

        <Box
          component="ul"
          sx={{
            m: 0,
            p: 0,
            listStyle: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          {BENEFITS.map(benefit => (
            <Box
              component="li"
              key={benefit}
              sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}
            >
              <CheckIcon fontSize="small" color="primary" />
              <Typography variant="body2">{benefit}</Typography>
            </Box>
          ))}
        </Box>

        <Box>
          <Button variant="contained" onClick={openPricing}>
            {lapsed ? 'Renew Enterprise' : 'Learn about Enterprise'}
          </Button>
        </Box>

        {!lapsed && (
          <Typography variant="caption" color="text.secondary">
            Self-hosting? The audit log is included in the Enterprise licence.
          </Typography>
        )}
      </Box>
    </SectionCard>
  );
}
