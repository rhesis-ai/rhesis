'use client';

import { Can } from '@/components/common/Can';
import { CreatedMetadataPlaceholder } from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop } from '@/components/loading/TextPlaceholder';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_ICONS, TAB_KEYS, TAB_LABELS } from './components/tabs';

/** The test set page, its Basic Information tab drawn with the record's
 *  values pending. */
export default function TestSetDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.testSets)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        // TestSetHeaderActions; Sync from Garak shows only for Garak sets.
        actions={
          <FabGroup>
            <Can capability={Capability.TestSet.DELETE}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.TestSet.EXPORT}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.TestSet.EXECUTE}>
              <Fab icon={null} />
            </Can>
          </FabGroup>
        }
      >
        <DetailTabNav
          tabs={TAB_KEYS.map(key => {
            const Icon = TAB_ICONS[key];
            return {
              key,
              label: TAB_LABELS[key],
              ...(Icon && { icon: <Icon /> }),
            };
          })}
          activeIndex={0}
          onChange={noop}
          aria-label="Test set detail tabs"
        />
        <DetailTabPanel value={0} index={0} prefix="test-set-detail">
          <SectionPlaceholder
            title="Test set details"
            editable
            fields={['Name', 'Description']}
            columns={1}
          />
          <SectionPlaceholder title="Metrics & tags" editable />
        </DetailTabPanel>
      </PageLayout>
    </SkeletonMode>
  );
}
