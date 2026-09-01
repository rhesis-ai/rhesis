import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';
import SkeletonPageHeader from '@/components/loading/SkeletonPageHeader';

// Without this file the fallback is the catch-all list skeleton, now visible
// while the page awaits its requirements, topics and categories. The writer
// does render a PageLayout header (2-segment trail, three FABs: export, add,
// save), but its table swaps between a 5- and an 8-column layout with the
// test-type toggle, so there is no one row shape to draw: a spinner is the
// honest placeholder there, as on playground.
export default function ManualTestWriterLoading() {
  return (
    <DelayedReveal>
      <SkeletonPageHeader actionCount={3} breadcrumbCount={2} />
      <PageLoadingState />
    </DelayedReveal>
  );
}
