import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';

// Without this file the nearest fallback is test-sets/loading.tsx, which draws
// the test-set *list* and sits above this route's layout — so the whole
// generation wizard, header included, was replaced by a grid skeleton while
// the page awaited its models and sources. Scoping the boundary here lets
// layout.tsx paint the real PageLayout header immediately; only the body
// waits. That body is a chat-style wizard with no predictable shape, so a
// spinner is the honest placeholder, as on playground.
export default function GenerateTestSetLoading() {
  return (
    <DelayedReveal>
      <PageLoadingState />
    </DelayedReveal>
  );
}
