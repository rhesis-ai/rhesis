import DelayedReveal from '@/components/loading/DelayedReveal';
import PageLoadingState from '@/components/common/PageLoadingState';

// Architect is full-bleed, so a centered spinner fits better than the
// PageLayout-shaped skeletons. DelayedReveal gives it the same hold, so a
// fast navigation shows only the top progress bar.
export default function ArchitectLoading() {
  return (
    <DelayedReveal sx={{ height: '100%' }}>
      <PageLoadingState />
    </DelayedReveal>
  );
}
