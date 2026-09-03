import PageListSkeleton from '@/components/loading/PageListSkeleton';

// Test Sets shows 4 header FABs (import, security scan, generate, create) for a
// fully-permissioned user; the catch-all skeleton's default of 2 undercounts it.
export default function TestSetsLoading() {
  return <PageListSkeleton actionCount={4} />;
}
