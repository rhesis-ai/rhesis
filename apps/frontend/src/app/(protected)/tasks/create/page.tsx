import { redirect } from 'next/navigation';

interface CreateTaskRedirectPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/** Redirect legacy /tasks/create URLs to the overview drawer. */
export default async function CreateTaskRedirectPage({
  searchParams,
}: CreateTaskRedirectPageProps) {
  const params = await searchParams;
  const qs = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      value.forEach(v => qs.append(key, v));
    } else if (value !== undefined) {
      qs.append(key, value);
    }
  }

  qs.set('create', 'true');
  redirect(`/tasks?${qs.toString()}`);
}
