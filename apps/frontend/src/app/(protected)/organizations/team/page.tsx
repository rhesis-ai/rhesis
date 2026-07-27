import { redirect } from 'next/navigation';

interface TeamPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/** Legacy route — team management now lives under Organization Settings. */
export default async function TeamPage({ searchParams }: TeamPageProps) {
  const params = await searchParams;
  const qs = new URLSearchParams({ tab: 'team' });

  if (typeof params.tour === 'string') {
    qs.set('tour', params.tour);
  }

  redirect(`/organizations/settings?${qs.toString()}`);
}
