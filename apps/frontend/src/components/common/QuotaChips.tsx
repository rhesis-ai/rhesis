'use client';

import Button from '@mui/material/Button';
import { BORDER_RADIUS } from '@/styles/theme';
import { UPGRADE_URL } from '@/constants/quota';

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
