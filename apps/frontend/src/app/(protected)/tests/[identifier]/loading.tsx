'use client';

import Grid from '@mui/material/Grid';
import { Can } from '@/components/common/Can';
import { CreatedMetadataPlaceholder } from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import { SectionCard } from '@/components/common/SectionCard';
import { SectionEditButton } from '@/components/common/SectionCardActions';
import ViewField from '@/components/common/ViewField';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop, PLACEHOLDER_TEXT } from '@/components/loading/TextPlaceholder';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_ICONS, TAB_KEYS, TAB_LABELS } from './components/tabs';

/** TestMetadataCard's read-only fields and their widths. */
const TEST_DETAIL_FIELDS = [
  { label: 'Requirement', md: 3 },
  { label: 'Type', md: 3 },
  { label: 'Topic', md: 6 },
  { label: 'Category', md: 6 },
  { label: 'Priority', md: 6 },
];

/** The test page, its Overview tab drawn with the record's values pending. */
export default function TestDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.tests)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        // TestToTestSet's buttons; Go to Parent shows only for a child test.
        actions={
          <FabGroup>
            <Can capability={Capability.Test.DELETE}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.Test.CREATE}>
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
          aria-label="Test detail tabs"
        />
        <DetailTabPanel value={0} index={0} prefix="test-detail">
          <SectionCard
            title="Test details"
            actions={<SectionEditButton onClick={noop} />}
          >
            <Grid container columnSpacing={4} rowSpacing={6}>
              {TEST_DETAIL_FIELDS.map(({ label, md }) => (
                <Grid key={label} size={{ xs: 12, sm: 6, md }}>
                  <ViewField
                    label={label}
                    value={PLACEHOLDER_TEXT.value}
                    helperText="Infotext"
                  />
                </Grid>
              ))}
            </Grid>
          </SectionCard>
          <SectionPlaceholder title="Test input" editable />
        </DetailTabPanel>
      </PageLayout>
    </SkeletonMode>
  );
}
