import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';
import SkeletonPageHeader from '@/components/loading/SkeletonPageHeader';
import { PAGE_HEADERS } from '@/constants/page-headers';

// Playground is a chat interface, so its body has no predictable shape to
// skeleton: a spinner is the honest placeholder there. Its header is fixed, so
// it is drawn for real at once.
export default function PlaygroundLoading() {
  return (
    <>
      <SkeletonPageHeader {...PAGE_HEADERS.playground} />
      <DelayedReveal>
        <PageLoadingState />
      </DelayedReveal>
    </>
  );
}
