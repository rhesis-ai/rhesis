'use client';

import Box from '@mui/material/Box';
import { Can } from '@/components/common/Can';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import { DetailTabPanel } from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop, PLACEHOLDER_TEXT } from '@/components/loading/TextPlaceholder';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS } from './components/tabs';

/** The experiment page, its Overview tab drawn with the record's values
 *  pending. */
export default function ExperimentDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.experiments)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={
          <DetailMetadataStrip
            items={[
              { label: 'Created', value: PLACEHOLDER_TEXT.date },
              { label: 'Versions', value: PLACEHOLDER_TEXT.count },
              { label: 'Visibility', value: PLACEHOLDER_TEXT.crumb },
            ]}
          />
        }
        actions={
          <FabGroup>
            <Can capability={Capability.TestRun.CREATE}>
              <Fab icon={null} />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <DetailTabNav
            tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
            activeIndex={0}
            onChange={noop}
            aria-label="Experiment detail sections"
          />
          <DetailTabPanel value={0} index={0} prefix="experiment">
            <SectionPlaceholder
              title="Experiment Overview"
              editable
              fields={['Description', 'Project', 'Visibility']}
            />
            <SectionPlaceholder
              title="Experiment Iterations"
              fields={['Latest Version', 'Total Versions', 'Last Saved']}
            />
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
