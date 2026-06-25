'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

/** Deep-link entry: opens the create drawer with project pre-selected. */
export default function NewProjectEndpointPage() {
  const router = useRouter();
  const params = useParams<{ identifier: string }>();

  useEffect(() => {
    const projectId = params?.identifier;
    if (projectId) {
      router.replace(`/endpoints?create=1&projectId=${projectId}`);
    } else {
      router.replace('/endpoints?create=1');
    }
  }, [router, params?.identifier]);

  return null;
}
