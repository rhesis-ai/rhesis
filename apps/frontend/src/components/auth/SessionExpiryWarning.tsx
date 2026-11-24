'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import { handleSignOut } from '@/actions/auth';

/** How long before the session ends the warning appears (WCAG 2.2.1 asks for at least 20 s). */
export const SESSION_WARNING_LEAD_MS = 2 * 60 * 1000;
const IDLE_CHECK_MS = 10 * 1000;
const COUNTDOWN_TICK_MS = 1000;

function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes > 0
    ? `${minutes}:${String(seconds).padStart(2, '0')} minutes`
    : `${seconds} seconds`;
}

/**
 * Warns before the session ends and lets the user extend it with one click
 * (WCAG 2.2.1). Checks the clock on an interval rather than one long timeout,
 * so a laptop waking from sleep still gets the right state.
 */
export default function SessionExpiryWarning() {
  const { data: session, update } = useSession();
  const expiresAt = session?.expires ? Date.parse(session.expires) : NaN;
  const [remaining, setRemaining] = React.useState<number | null>(null);
  const [extending, setExtending] = React.useState(false);
  // Read by the interval, so an extension in flight holds off the redirect.
  const extendingRef = React.useRef(false);
  const [extendFailed, setExtendFailed] = React.useState(false);

  const open = remaining !== null && remaining <= SESSION_WARNING_LEAD_MS;

  React.useEffect(() => {
    if (Number.isNaN(expiresAt)) return;
    const tick = () => {
      const left = expiresAt - Date.now();
      if (left <= 0) {
        if (extendingRef.current) return;
        window.location.assign('/auth/signin?session_expired=true');
        return;
      }
      setRemaining(left);
    };
    tick();
    const id = window.setInterval(
      tick,
      open ? COUNTDOWN_TICK_MS : IDLE_CHECK_MS
    );
    // Background tabs throttle intervals; check as soon as the tab is back.
    const onVisible = () => {
      if (document.visibilityState === 'visible') tick();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [expiresAt, open]);

  const staySignedIn = async () => {
    setExtending(true);
    extendingRef.current = true;
    setExtendFailed(false);
    try {
      // Re-issues the session cookie with a fresh expiry.
      const next = await update();
      if (!next) setExtendFailed(true);
    } catch {
      setExtendFailed(true);
    } finally {
      setExtending(false);
      extendingRef.current = false;
    }
  };

  if (!open) return null;

  return (
    <Dialog
      open
      slotProps={{ paper: { role: 'alertdialog' } }}
      aria-labelledby="session-expiry-title"
      aria-describedby="session-expiry-description"
    >
      <DialogTitle id="session-expiry-title">
        Your session is about to end
      </DialogTitle>
      <DialogContent>
        <DialogContentText id="session-expiry-description">
          For your security you will be signed out in about{' '}
          {remaining !== null && remaining > 60 * 1000
            ? '2 minutes'
            : 'a minute'}
          . Unsaved changes may be lost.
        </DialogContentText>
        {/* Visible countdown only; not live, so screen readers aren't
            interrupted every second. */}
        <DialogContentText aria-hidden sx={{ mt: 2, fontWeight: 600 }}>
          Time left: {formatRemaining(remaining ?? 0)}
        </DialogContentText>
        {extendFailed && (
          <DialogContentText role="alert" color="error" sx={{ mt: 2 }}>
            Your session couldn&apos;t be extended. Save your work and sign in
            again.
          </DialogContentText>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => handleSignOut()}>Sign out</Button>
        <Button
          variant="contained"
          onClick={staySignedIn}
          disabled={extending}
          // eslint-disable-next-line jsx-a11y/no-autofocus -- the safe choice gets focus
          autoFocus
        >
          Stay signed in
        </Button>
      </DialogActions>
    </Dialog>
  );
}
