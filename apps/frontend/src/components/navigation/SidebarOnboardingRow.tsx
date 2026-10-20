'use client';

import React, { useEffect, useState } from 'react';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Popover from '@mui/material/Popover';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { REQUIRED_ONBOARDING_STEPS } from '@/config/onboarding-tours';
import OnboardingChecklist from '@/components/onboarding/OnboardingChecklist';
import {
  POPOVER_PAPER_SX,
  collapsedNavItemSx,
  navCardIconSx,
  navCardLabelSx,
  navCardRowSx,
} from './sidebar-utils';

const RING_SIZE = 22;
const RING_THICKNESS = 5;

/** A determinate ring over a full-circle track. */
function ProgressRing({ value }: { value: number }) {
  return (
    <Box sx={{ position: 'relative', display: 'flex' }}>
      <CircularProgress
        variant="determinate"
        value={100}
        size={RING_SIZE}
        thickness={RING_THICKNESS}
        sx={{ color: (theme: Theme) => theme.palette.greyscale.border }}
        aria-hidden="true"
      />
      <CircularProgress
        variant="determinate"
        value={value}
        size={RING_SIZE}
        thickness={RING_THICKNESS}
        sx={{ position: 'absolute', left: 0, top: 0 }}
        aria-hidden="true"
      />
    </Box>
  );
}

interface SidebarOnboardingRowProps {
  collapsed?: boolean;
}

/** "Getting started" row in the sidebar footer card; opens the checklist in a popover. */
export function SidebarOnboardingRow({
  collapsed = false,
}: SidebarOnboardingRowProps) {
  const {
    progress,
    isComplete,
    completionPercentage,
    dismissOnboarding,
    checklistHidden,
  } = useOnboarding();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // Progress comes from localStorage, which the server can't read. Rendering
  // before mount makes the server HTML disagree with the client, and React
  // then rebuilds the whole protected layout.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Gone once dismissed or done, and while a full-screen step blocks the app
  if (!mounted || checklistHidden || progress.dismissed || isComplete) {
    return null;
  }

  const total = REQUIRED_ONBOARDING_STEPS.length;
  const doneCount = REQUIRED_ONBOARDING_STEPS.filter(
    step => progress[step.id]
  ).length;
  const label = `Getting started, ${doneCount} of ${total} done`;

  const ring = (
    <Box sx={navCardIconSx}>
      {collapsed ? (
        <Badge
          badgeContent={total - doneCount}
          color="primary"
          // Circular overlap keeps the badge inside the card, which clips
          overlap="circular"
        >
          <ProgressRing value={completionPercentage} />
        </Badge>
      ) : (
        <ProgressRing value={completionPercentage} />
      )}
    </Box>
  );

  const row = (
    <Box
      component="button"
      type="button"
      onClick={(e: React.MouseEvent<HTMLElement>) => setAnchor(e.currentTarget)}
      aria-label={label}
      aria-haspopup="dialog"
      aria-expanded={Boolean(anchor)}
      sx={{
        ...navCardRowSx(),
        ...(collapsed ? collapsedNavItemSx : {}),
        background: 'none',
        border: 'none',
        borderBottom: (theme: Theme) =>
          `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: 0,
        alignSelf: 'stretch',
        textAlign: 'left',
        font: 'inherit',
      }}
    >
      {ring}
      {!collapsed && (
        <Box sx={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Typography
            variant="bodyMReg"
            sx={{
              ...navCardLabelSx,
              color: (theme: Theme) => theme.palette.greyscale.body,
            }}
          >
            Getting started
          </Typography>
          <Typography
            variant="caption"
            aria-hidden="true"
            sx={{ color: (theme: Theme) => theme.palette.greyscale.subtitle }}
          >
            {doneCount} of {total} done
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    <>
      {collapsed ? (
        <Tooltip
          title={`Getting started · ${doneCount} of ${total} done`}
          placement="right"
        >
          {row}
        </Tooltip>
      ) : (
        row
      )}

      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{
          paper: { sx: { ...POPOVER_PAPER_SX, ml: 1.5 } },
        }}
      >
        <OnboardingChecklist
          onStepSelected={() => setAnchor(null)}
          onDismiss={() => {
            setAnchor(null);
            setConfirmOpen(true);
          }}
        />
      </Popover>

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        aria-labelledby="dismiss-onboarding-title"
        aria-describedby="dismiss-onboarding-description"
      >
        <DialogTitle id="dismiss-onboarding-title">
          Hide the getting started guide?
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="dismiss-onboarding-description">
            It won&apos;t come back after you hide it.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            onClick={() => {
              dismissOnboarding();
              setConfirmOpen(false);
            }}
            variant="contained"
            autoFocus
          >
            Hide
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default SidebarOnboardingRow;
