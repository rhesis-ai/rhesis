'use client';

import PageCardGridSkeleton from '@/components/loading/PageCardGridSkeleton';
import { modelsDescription, PAGE_HEADERS } from '@/constants/page-headers';
import {
  useEmbeddingsEnabled,
  useRhesisKeyEnabled,
} from '@/contexts/FeaturesContext';

// models renders a grid of EntityCards, not a DataGrid, so the catch-all
// table skeleton would be the wrong shape here. Its description and its
// platform-key button follow feature flags, read here as the page reads them.
export default function ModelsLoading() {
  const embeddingsEnabled = useEmbeddingsEnabled();
  const rhesisKeyEnabled = useRhesisKeyEnabled();
  const header = PAGE_HEADERS.models;
  return (
    <PageCardGridSkeleton
      header={{
        title: header.title,
        description: modelsDescription(embeddingsEnabled),
        actions: rhesisKeyEnabled ? [null, ...header.actions] : header.actions,
      }}
    />
  );
}
