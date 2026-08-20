'use client';

import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import { BORDER_RADIUS } from '@/styles/theme';
import { UPGRADE_URL } from '@/constants/quota';
import { isCommunityEdition } from '@/utils/quota';

/** Plan pill (e.g. "Community", "Enterprise"). Shared by the usage page
 * and the org-menu usage block so the two never drift on styling. No
 * "plan" suffix -- the org-menu block is space-constrained, and the chip
 * already reads as a plan in context. */
export function PlanChip({ edition }: { edition: string }) {
  const label = `${edition.charAt(0).toUpperCase()}${edition.slice(1)}`;
  return (
    <Chip
      label={label}
      size="small"
      color={isCommunityEdition(edition) ? 'default' : 'primary'}
      sx={{ borderRadius: BORDER_RADIUS.pill, fontWeight: 600 }}
    />
  );
}

/** "Upgrade" button/link -- always the same destination, everywhere it
 * appears. Only ever shown to org admins; callers gate that. */
export function UpgradeLink() {
  return (
    <Button
      component="a"
      href={UPGRADE_URL}
      target="_blank"
      rel="noopener noreferrer"
      variant="outlined"
      size="small"
      sx={{ borderRadius: BORDER_RADIUS.sm, fontWeight: 600 }}
    >
      Upgrade
    </Button>
  );
}
