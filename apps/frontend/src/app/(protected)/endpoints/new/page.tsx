'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Deep-link entry: opens the create drawer on the endpoints list. */
export default function NewEndpointPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/endpoints?create=1');
  }, [router]);

  return null;
}
