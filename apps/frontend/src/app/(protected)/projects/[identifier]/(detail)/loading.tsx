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
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { SECTION_GRID } from '@/styles/theme-constants';
import { normalizeTabParam, TAB_KEYS, TAB_LABELS } from '../components/tabs';

/** ProjectMetadataCard's read-only fields and their widths. */
const PROJECT_FIELDS = [
  { label: 'Project ID', size: { xs: 12 } },
  { label: 'Name', size: { xs: 12, sm: 6, md: 6 } },
  { label: 'Status', size: { xs: 12, sm: 6, md: 3 } },
  { label: 'Owner', size: { xs: 12, md: 3 } },
  { label: 'Description', size: { xs: 12 } },
];

/** The project page with the project's values pending; the Overview tab
 *  draws its cards, the other tabs a neutral card. */
export default function ProjectDetailLoading() {
  const activeKey = normalizeTabParam(useSearchParams().get('tab'));
  const activeTab = TAB_KEYS.indexOf(activeKey);

  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.projects)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        actions={
          <FabGroup>
            <Can capability={Capability.Project.UPDATE}>
              <Fab icon={null} />
            </Can>
            <Can capability={Capability.Project.UPDATE}>
              <Fab icon={null} />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <DetailTabNav
            tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
            activeIndex={activeTab}
            onChange={noop}
            aria-label="Project detail sections"
          />
          <DetailTabPanel
            value={activeTab}
            index={activeTab}
            prefix="project-detail"
          >
            {activeKey === 'overview' ? (
              <>
                <SectionCard
                  title="Project details"
                  actions={<SectionEditButton onClick={noop} />}
                >
                  <Grid
                    container
                    columnSpacing={SECTION_GRID.columnSpacing}
                    rowSpacing={SECTION_GRID.rowSpacing}
                    alignItems="flex-start"
                  >
                    {PROJECT_FIELDS.map(({ label, size }) => (
                      <Grid key={label} size={size}>
                        <ViewField
                          label={label}
                          value={PLACEHOLDER_TEXT.value}
                        />
                      </Grid>
                    ))}
                  </Grid>
                </SectionCard>
                <SectionPlaceholder title="Tags" editable />
              </>
            ) : (
              <SectionPlaceholder />
            )}
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
