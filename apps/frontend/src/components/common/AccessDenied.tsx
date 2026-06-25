'use client';

import React from 'react';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import EntityEmptyState from './EntityEmptyState';
import { CAPABILITY_LABELS } from '@/constants/capabilities';

interface AccessDeniedProps {
  /** The `resource:action` capability that is required. Shown as a human label. */
  requiredPermission?: string;
  /** Override the default description. */
  description?: string;
  /** Optional CTA shown as an outlined button. */
  actionLabel?: string;
  onAction?: () => void;
}

/**
 * Full-page or section-level access denied state.
 *
 * Uses `EntityEmptyState` (card variant) with a lock icon: blue icon,
 * blue headline, grey body, outlined CTA — matches the mockup's Access-Denied
 * pattern. Fail-closed: renders while permissions are still loading.
 */
export default function AccessDenied({
  requiredPermission,
  description,
  actionLabel,
  onAction,
}: AccessDeniedProps) {
  const permLabel = requiredPermission
    ? (CAPABILITY_LABELS[requiredPermission] ?? requiredPermission)
    : undefined;

  const resolvedDescription =
    description ??
    (permLabel
      ? `You need the "${permLabel}" permission to access this.`
      : 'You do not have permission to access this.');

  return (
    <EntityEmptyState
      icon={LockOutlinedIcon}
      title="Access Denied"
      description={resolvedDescription}
      actionLabel={actionLabel}
      onAction={onAction}
      card
    />
  );
}
