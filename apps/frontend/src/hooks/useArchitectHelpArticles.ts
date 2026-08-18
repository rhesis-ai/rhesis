'use client';

import { useQuery } from '@tanstack/react-query';
import { architectHelpKeys } from '@/constants/query-keys';

interface ArchitectHelpResponse {
  articleUrls: string[];
}

/**
 * Docs URLs for the Architect welcome help cards, served by /api/architect-help
 * from the container environment. Deployment config, so it only changes on a
 * rollout — never refetch it during a session.
 */
export function useArchitectHelpArticles() {
  return useQuery<string[]>({
    queryKey: architectHelpKeys.all(),
    queryFn: async () => {
      const response = await fetch('/api/architect-help');
      if (!response.ok) return [];
      const data = (await response.json()) as ArchitectHelpResponse;
      return data.articleUrls ?? [];
    },
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}
