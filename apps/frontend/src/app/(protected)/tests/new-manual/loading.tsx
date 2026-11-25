import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';
import SkeletonPageHeader from '@/components/loading/SkeletonPageHeader';
import {
  directoryCrumb,
  MANUAL_TEST_WRITER_HEADER,
  PAGE_HEADERS,
} from '@/constants/page-headers';

// The writer's header is fixed, so it is drawn for real at once. Its table
// swaps between a 5- and an 8-column layout with the test-type toggle, so there
// is no one row shape to draw: a spinner is the honest placeholder there, as
// on playground.
export default function ManualTestWriterLoading() {
  return (
    <>
      <SkeletonPageHeader
        breadcrumbCount={2}
        crumbs={[
          directoryCrumb(PAGE_HEADERS.tests),
          { label: MANUAL_TEST_WRITER_HEADER.title },
        ]}
        title={MANUAL_TEST_WRITER_HEADER.title}
        description={MANUAL_TEST_WRITER_HEADER.description}
        actions={MANUAL_TEST_WRITER_HEADER.actions}
      />
      <DelayedReveal>
        <PageLoadingState />
      </DelayedReveal>
    </>
  );
}
