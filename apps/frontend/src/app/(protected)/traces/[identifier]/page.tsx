export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';

interface TraceByIdPageProps {
  params: Promise<{ identifier: string }>;
}

/**
 * Server component that resolves a trace span DB UUID to the traces page
 * with the drawer auto-opened for the correct trace.
 *
 * This enables "Go to Trace" navigation from tasks and comments.
 */
export default async function TraceByIdPage({ params }: TraceByIdPageProps) {
  const { identifier } = await params;

  await requireSession();

  const clientFactory = await createServerApiFactory();
  const client = clientFactory.getTelemetryClient();
  const lookup = await client.lookupSpan(identifier);

  redirect(
    `/traces?open_trace=${encodeURIComponent(lookup.trace_id)}&project_id=${encodeURIComponent(lookup.project_id)}`
  );
}
