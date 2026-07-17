'use client';

import React, { useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Fab, FabAddIcon } from '@/components/common/Fab';
import TestSetDrawer from './components/TestSetDrawer';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

/**
 * Client component that owns the "New Test Set" Fab and the creation drawer.
 * Rendered inside the server-component test-sets page so that the action
 * button is available in the PageLayout header without making the whole page
 * a client component.
 */
export function TestSetsNewAction() {
  const { status } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Fab
        icon={<FabAddIcon />}
        tooltip="New Test Set"
        onClick={() => setOpen(true)}
        disabled={!isAuthenticated(status)}
      />
      {isAuthenticated(status) && (
        <TestSetDrawer
          open={open}
          onClose={() => setOpen(false)}
          onSuccess={() => {
            setOpen(false);
            router.refresh();
          }}
        />
      )}
    </>
  );
}
