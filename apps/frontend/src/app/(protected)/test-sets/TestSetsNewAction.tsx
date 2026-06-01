'use client';

import React, { useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import AddIcon from '@mui/icons-material/Add';
import { Fab } from '@/components/common/Fab';
import TestSetDrawer from './components/TestSetDrawer';

/**
 * Client component that owns the "New Test Set" Fab and the creation drawer.
 * Rendered inside the server-component test-sets page so that the action
 * button is available in the PageLayout header without making the whole page
 * a client component.
 */
export function TestSetsNewAction() {
  const { data: session } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const sessionToken = session?.session_token ?? '';

  return (
    <>
      <Fab
        icon={<AddIcon />}
        tooltip="New Test Set"
        onClick={() => setOpen(true)}
        disabled={!sessionToken}
      />
      {sessionToken && (
        <TestSetDrawer
          open={open}
          onClose={() => setOpen(false)}
          sessionToken={sessionToken}
          onSuccess={() => {
            setOpen(false);
            router.refresh();
          }}
        />
      )}
    </>
  );
}
