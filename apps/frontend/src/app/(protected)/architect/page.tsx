import { Metadata } from 'next';
import ArchitectClient from './components/ArchitectClient';
import { requireSession } from '@/utils/require-session';

export const metadata: Metadata = {
  title: 'Architect',
};

/**
 * Server component: renders immediately after the auth gate so the welcome
 * screen streams with the layout instead of waiting for backend prefetches.
 *
 * Sessions and the endpoint existence check load client-side — the sidebar
 * starts collapsed, so a brief loading window there is invisible, and the
 * chips render optimistically (hidden only once the client confirms the
 * project has no endpoints).
 */
export default async function ArchitectPage() {
  await requireSession();
  return <ArchitectClient />;
}
