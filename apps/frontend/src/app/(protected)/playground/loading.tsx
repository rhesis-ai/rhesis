import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';
import SkeletonPageHeader from '@/components/loading/SkeletonPageHeader';

// Playground is a chat interface, so its body has no predictable shape to
// skeleton: a spinner is the honest placeholder there. It does render a
// PageLayout header with two FABs though, unlike architect, so the header is
// worth drawing.
export default function PlaygroundLoading() {
  return (
    <DelayedReveal>
      <SkeletonPageHeader actionCount={2} />
      <PageLoadingState />
    </DelayedReveal>
  );
}
