import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import { requireSession } from '@/utils/require-session';
import ReportDetailClient from './components/ReportDetailClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export const metadata: Metadata = { title: 'Report' };

export default async function ReportDetailPage({ params }: PageProps) {
  await requireSession();
  const { identifier } = await params;
  const factory = await createServerApiFactory();
  let report;
  try {
    report = await factory.getReportsClient().getReport(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }
  return <ReportDetailClient initialReport={report} />;
}
