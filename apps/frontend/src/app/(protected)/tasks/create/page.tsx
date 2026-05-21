'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/** Redirect legacy /tasks/create URLs to the overview drawer. */
export default function CreateTaskRedirectPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('create', 'true');
    router.replace(`/tasks?${params.toString()}`);
  }, [router, searchParams]);

  return null;
}
