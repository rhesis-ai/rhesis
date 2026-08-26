import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import type { ArchitectSession } from '@/utils/api-client/architect-client';
import ArchitectClient from './components/ArchitectClient';

export const metadata: Metadata = {
  title: 'Architect',
};

/**
 * Server component: fetches the session list before rendering so the sidebar
 * arrives populated -- no client-side spinner on first load. Fails open to
 * "no initial data" so the client falls back to its own fetch.
 */
export default async function ArchitectPage() {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('No session token available');
  }

  let initialSessions: ArchitectSession[] | undefined;
  if (await hasServerCapability(Capability.Architect.READ)) {
    try {
      const factory = await createServerApiFactory();
      const sessions = await factory.getArchitectClient().getSessions();
      initialSessions = JSON.parse(JSON.stringify(sessions));
    } catch {
      initialSessions = undefined;
    }
  }

  return <ArchitectClient initialSessions={initialSessions} />;
}
