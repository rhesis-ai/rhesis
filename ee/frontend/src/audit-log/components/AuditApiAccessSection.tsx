'use client';

import * as React from 'react';
import Link from 'next/link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useQuery } from '@tanstack/react-query';
import { useCan } from '@/components/common/Can';
import { useNotifications } from '@/components/common/NotificationContext';
import { SectionCard } from '@/components/common/SectionCard';
import { Capability } from '@/constants/capabilities';
import { FeatureName } from '@/constants/features';
import { useFeature } from '@/contexts/FeaturesContext';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { getApiErrorMessage } from '@/utils/error-utils';
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { fetchRoles } from '../../rbac/api/role-cache';
import { getRoleChipSx } from '../../rbac/role-display';
import {
  AUDIT_EVENTS_MAX_LIMIT,
  AUDIT_EVENTS_PATH,
} from '../api/audit-log-client';
import { auditLogQueryKeys } from '../filters';
import { monoSx } from './AuditChanges';

const ROLES_TAB_URL = '/organizations/settings?tab=roles';
const BASE_URL_PLACEHOLDER = 'https://<your-rhesis-api>';
const EXAMPLE_DAYS_BACK = 30;

function apiBaseUrl(): string {
  try {
    return getClientApiBaseUrl().replace(/\/+$/, '');
  } catch {
    return BASE_URL_PLACEHOLDER;
  }
}

/** The list call in the platform's conventions: OData `$filter`, `limit` up to 100. */
export function exampleRequest(baseUrl: string, since: Date): string {
  const day = since.toISOString().slice(0, 10);
  return [
    `curl -G "${baseUrl}${AUDIT_EVENTS_PATH}" \\`,
    '  -H "Authorization: Bearer $RHESIS_API_TOKEN" \\',
    `  --data-urlencode "\\$filter=startswith(action,'endpoint.') and occurred_at ge ${day}" \\`,
    `  --data-urlencode "limit=${AUDIT_EVENTS_MAX_LIMIT}"`,
  ].join('\n');
}

function RolesWithAccess() {
  const rbacOn = useFeature(FeatureName.RBAC);
  const canReadRoles = useCan(Capability.Role.READ);
  const {
    data: roles,
    isLoading,
    error,
  } = useQuery({
    queryKey: auditLogQueryKeys.roles(),
    queryFn: () => fetchRoles(),
    enabled: rbacOn && canReadRoles,
  });

  if (!rbacOn || !canReadRoles) {
    return (
      <Typography variant="body2" color="text.secondary">
        Owners and Admins can read the audit log.
      </Typography>
    );
  }
  if (isLoading) return <CircularProgress size={20} />;
  if (error) {
    return (
      <Alert severity="error">
        {getApiErrorMessage(error, 'Could not load the roles.')}
      </Alert>
    );
  }

  const withAccess = (roles ?? [])
    .filter(role =>
      role.permissions.some(p => p.name === Capability.AuditLog.READ)
    )
    .sort((a, b) => b.level - a.level);

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
      {withAccess.map(role => (
        <Chip
          key={role.id}
          size="small"
          label={role.display_name}
          sx={getRoleChipSx(role)}
        />
      ))}
    </Box>
  );
}

/** How to read the log over the API, and who may. Stores nothing. */
export default function AuditApiAccessSection() {
  const { show } = useNotifications();
  const example = React.useMemo(() => {
    const since = new Date();
    since.setDate(since.getDate() - EXAMPLE_DAYS_BACK);
    return exampleRequest(apiBaseUrl(), since);
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(example);
      show('Copied', { severity: 'success' });
    } catch {
      show('Could not copy', { severity: 'error' });
    }
  };

  return (
    <>
      <SectionCard
        title="Read the log over the API"
        subtitle="GET /audit-events takes the same $filter, skip, limit and sort_by as every other list. Each page is recorded as a read of the log."
      >
        <Box
          sx={{
            position: 'relative',
            p: 2,
            pr: 6,
            borderRadius: BORDER_RADIUS.sm,
            bgcolor: theme => theme.palette.greyscale.surface2,
          }}
        >
          <Box component="pre" sx={{ ...monoSx, m: 0, whiteSpace: 'pre-wrap' }}>
            {example}
          </Box>
          <Tooltip title="Copy">
            <IconButton
              aria-label="Copy example"
              size="small"
              onClick={copy}
              sx={{
                position: 'absolute',
                top: theme => theme.spacing(1),
                right: theme => theme.spacing(1),
              }}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Use an API token whose owner can read the audit log. A token limited
          to chosen scopes needs the{' '}
          <Box component="code" sx={monoSx}>
            {Capability.AuditLog.READ}
          </Box>{' '}
          scope.
        </Typography>
      </SectionCard>

      <SectionCard
        title="Who can read the log"
        subtitle="Roles that include reading the audit log. Change them in the role editor."
        actions={
          <Button component={Link} href={ROLES_TAB_URL} size="small">
            Open Roles
          </Button>
        }
      >
        <RolesWithAccess />
      </SectionCard>
    </>
  );
}
