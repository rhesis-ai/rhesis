import { requireSession } from '@/utils/require-session';
import SchedulePageClient from './components/SchedulePageClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function SchedulePage({ params }: PageProps) {
  await requireSession();
  const { identifier } = await params;
  return <SchedulePageClient scheduleId={identifier} />;
}
