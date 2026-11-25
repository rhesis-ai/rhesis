import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';

// Routes without a loading view of their own: a page renders itself as its
// loading view (see SkeletonMode), so a route that doesn't gets a neutral
// spinner rather than a guess at its shape.
export default function ProtectedLoading() {
  return (
    <DelayedReveal>
      <PageLoadingState />
    </DelayedReveal>
  );
}
