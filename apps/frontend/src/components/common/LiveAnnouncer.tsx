'use client';

import * as React from 'react';
import VisuallyHidden from './VisuallyHidden';

export type Politeness = 'polite' | 'assertive';
type Announce = (message: string, politeness?: Politeness) => void;

const AnnounceContext = React.createContext<Announce>(() => {});

// Long enough for screen readers to register the cleared region first, so a
// repeated message is read again.
const SET_DELAY_MS = 100;

/**
 * Screen-reader announcements that work when the message's own element is
 * new or about to unmount. Live regions only speak when content changes inside
 * a region that already exists, so this one stays mounted for the whole app.
 */
export function LiveAnnouncerProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [polite, setPolite] = React.useState('');
  const [assertive, setAssertive] = React.useState('');
  const timer = React.useRef<number | undefined>(undefined);

  const announce = React.useCallback<Announce>(
    (message, politeness = 'polite') => {
      const set = politeness === 'assertive' ? setAssertive : setPolite;
      set('');
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => set(message), SET_DELAY_MS);
    },
    []
  );

  React.useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <AnnounceContext.Provider value={announce}>
      {children}
      <VisuallyHidden role="status" aria-live="polite" aria-atomic="true">
        {polite}
      </VisuallyHidden>
      <VisuallyHidden aria-live="assertive" aria-atomic="true">
        {assertive}
      </VisuallyHidden>
    </AnnounceContext.Provider>
  );
}

/** Reads a message to screen reader users; does nothing visible. */
export function useAnnounce(): Announce {
  return React.useContext(AnnounceContext);
}
