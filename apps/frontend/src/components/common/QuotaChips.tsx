'use client';

import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import { BORDER_RADIUS } from '@/styles/theme';
import { UPGRADE_URL } from '@/constants/quota';
import { isCommunityEdition } from '@/utils/quota';

/** Plan pill (e.g. "community", "enterprise"). Shared by the usage page
 * and the org-menu usage block so the two never drift on styling. Lower
 * case, no "plan" suffix -- the org-menu block is space-constrained, and
 * the chip already reads as a plan in context.
 *
 * A paid plan whose licence is no longer active is marked "inactive" rather
 * than shown as though it were still in force. The backend holds such an org
 * to community limits while still reporting its old edition, so a plain
 * "enterprise" pill next to free-tier numbers is the one reading that leaves
 * an admin with no idea why their ceilings dropped.
 *
 * `licensed` is optional and defaults to "unknown" (`null`), which renders
 * exactly as before -- callers without the flag cannot accidentally label a
 * live plan inactive. */
export function PlanChip({
  edition,
  licensed = null,
}: {
  edition: string;
  licensed?: boolean | null;
}) {
  const isFreeTier = isCommunityEdition(edition);
  const isLapsed = licensed === false && !isFreeTier;
  const label = isLapsed
    ? `${edition.toLowerCase()} (inactive)`
    : edition.toLowerCase();
  return (
    <Chip
      label={label}
      size="small"
      color={isLapsed ? 'warning' : isFreeTier ? 'default' : 'primary'}
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
