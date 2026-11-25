'use client';

import Box from '@mui/material/Box';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import { Fab, FabGroup } from '@/components/common/Fab';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { PLACEHOLDER_TEXT } from '@/components/loading/TextPlaceholder';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';

/** The report page with the report's values pending. Its buttons depend on
 *  whether it is a draft and on the report's own permissions, so the header
 *  draws the common two (Export PDF and Publish or Copy). */
export default function ReportDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.reports)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={
          <DetailMetadataStrip
            items={[
              { label: 'status:', value: PLACEHOLDER_TEXT.crumb },
              { label: 'endpoint:', value: PLACEHOLDER_TEXT.crumb },
              { label: 'counting:', value: PLACEHOLDER_TEXT.crumb },
              { label: 'created by:', value: PLACEHOLDER_TEXT.person },
              { label: 'created on:', value: PLACEHOLDER_TEXT.date },
            ]}
          />
        }
        actions={
          <FabGroup>
            <Fab icon={null} />
            <Fab icon={null} />
          </FabGroup>
        }
      >
        <Box sx={{ flexGrow: 1 }}>
          <SectionPlaceholder
            title="Setup"
            subtitle="How the numbers below are counted and compared."
            editable
            fields={['Counting', 'Compared with', 'Type']}
            columns={3}
          />
          <SectionPlaceholder title="Summary" editable />
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
