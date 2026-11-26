import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { entityErrorView } from '@/utils/entity-error-view';
import { requireSession } from '@/utils/require-session';
import ReportDetailClient from './components/ReportDetailClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function ReportDetailPage({ params }: PageProps) {
  await requireSession();
  const { identifier } = await params;
  const factory = await createServerApiFactory();
  let report;
  try {
    report = await factory.getReportsClient().getReport(identifier);
  } catch (error) {
    const errorView = entityErrorView(error);
    if (errorView) return errorView;
    throw error;
  }
  return <ReportDetailClient initialReport={report} />;
}
