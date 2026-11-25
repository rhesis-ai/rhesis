'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { CreatedMetadataPlaceholder } from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import { SectionCard } from '@/components/common/SectionCard';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import {
  noop,
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import ScheduleRow from './components/ScheduleRow';
import { SCHEDULE_CRUMBS, TABS } from './components/tabs';

const SCHEDULE_ROWS = [
  'Repeats',
  'Runs as',
  'Time zone',
  'Ends',
  'Test set',
  'Endpoint',
  'Notify',
];

/** The schedule page, its Summary tab drawn with the schedule's values
 *  pending. Its buttons follow the schedule's state and permissions, so the
 *  header draws the common two (Run now and Edit). */
export default function ScheduleDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={SCHEDULE_CRUMBS}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        actions={
          <FabGroup>
            <Fab icon={null} />
            <Fab icon={null} />
          </FabGroup>
        }
      >
        <DetailTabNav
          tabs={TABS}
          activeIndex={0}
          onChange={noop}
          aria-label="Schedule sections"
        />
        <DetailTabPanel value={0} index={0} prefix="schedule">
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
              columnGap: 3,
            }}
          >
            <SectionCard title="Next run">
              <Typography variant="h6">
                <TextPlaceholder>{PLACEHOLDER_TEXT.value}</TextPlaceholder>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <TextPlaceholder>{PLACEHOLDER_TEXT.crumb}</TextPlaceholder>
              </Typography>
            </SectionCard>
            <SectionCard title="Schedule">
              {SCHEDULE_ROWS.map(label => (
                <ScheduleRow
                  key={label}
                  label={label}
                  value={
                    <TextPlaceholder>{PLACEHOLDER_TEXT.crumb}</TextPlaceholder>
                  }
                />
              ))}
            </SectionCard>
          </Box>
        </DetailTabPanel>
      </PageLayout>
    </SkeletonMode>
  );
}
