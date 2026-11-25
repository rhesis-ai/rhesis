'use client';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import { useSearchParams } from 'next/navigation';
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
import { SECTION_GRID } from '@/styles/theme-constants';
import { normalizeTabParam, TAB_KEYS, TAB_LABELS } from './components/tabs';

/** EndpointOverviewTab's read-only fields and their widths. */
const ENDPOINT_FIELDS = [
  { label: 'Name', size: { xs: 12, md: 6 } },
  { label: 'Project', size: { xs: 12, md: 6 } },
  { label: 'Description', size: { xs: 12 } },
  { label: 'Environment', size: { xs: 12, md: 6 } },
  { label: 'Timeout', size: { xs: 12, md: 6 } },
  { label: 'Tracing', size: { xs: 12, md: 6 } },
  { label: 'Connection type', size: { xs: 12, sm: 6, md: 4 } },
  { label: 'Status', size: { xs: 12, sm: 6, md: 4 } },
  { label: 'Config source', size: { xs: 12, sm: 6, md: 4 } },
];

/** The endpoint page with the endpoint's values pending. The trail depends on
 *  the endpoint (Projects › project › endpoint when it belongs to one,
 *  Endpoints › endpoint otherwise), so all of it waits. */
export default function EndpointDetailLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  const activeTab = TAB_KEYS.indexOf(activeKey);

  return (
    <SkeletonMode>
      <PageLayout
        pendingCrumbs={3}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        // EndpointHeaderActions.
        actions={
          <FabGroup>
            <Can capability={Capability.Playground.USE}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.Endpoint.CREATE}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.Endpoint.DELETE}>
              <Fab icon={null} />
            </Can>
          </FabGroup>
        }
      >
        <Box>
          <DetailTabNav
            tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
            activeIndex={activeTab}
            onChange={noop}
            aria-label="Endpoint detail tabs"
          />
          <DetailTabPanel
            value={activeTab}
            index={activeTab}
            prefix="endpoint-detail"
          >
            {activeKey === 'overview' ? (
              <SectionCard
                title="Endpoint details"
                actions={<SectionEditButton onClick={noop} />}
              >
                <Grid
                  container
                  columnSpacing={SECTION_GRID.columnSpacing}
                  rowSpacing={SECTION_GRID.rowSpacing}
                >
                  {ENDPOINT_FIELDS.map(({ label, size }) => (
                    <Grid key={label} size={size}>
                      <ViewField label={label} value={PLACEHOLDER_TEXT.value} />
                    </Grid>
                  ))}
                </Grid>
              </SectionCard>
            ) : (
              <SectionPlaceholder />
            )}
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
