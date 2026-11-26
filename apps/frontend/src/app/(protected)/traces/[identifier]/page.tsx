export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { entityErrorView } from '@/utils/entity-error-view';
import { traceDrawerHref } from '@/app/(protected)/traces/components/trace-links';

interface TraceByIdPageProps {
  params: Promise<{ identifier: string }>;
}

/**
 * Server component that resolves a trace span DB UUID to the traces page
 * with the drawer auto-opened on that span.
 *
 * This enables "Go to Trace" navigation from tasks and comments.
 */
export default async function TraceByIdPage({ params }: TraceByIdPageProps) {
  const { identifier } = await params;

  await requireSession();

  const clientFactory = await createServerApiFactory();
  const client = clientFactory.getTelemetryClient();
  let lookup;
  try {
    lookup = await client.lookupSpan(identifier);
  } catch (error) {
    const errorView = entityErrorView(error);
    if (errorView) return errorView;
    throw error;
  }

  redirect(
    traceDrawerHref({
      traceId: lookup.trace_id,
      projectId: lookup.project_id,
      spanId: lookup.span_id,
    })
  );
}
