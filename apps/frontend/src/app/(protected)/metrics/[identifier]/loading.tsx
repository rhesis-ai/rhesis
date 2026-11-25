'use client';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LinkIcon from '@mui/icons-material/Link';
import { Can } from '@/components/common/Can';
import DetailTabNav from '@/components/common/DetailTabNav';
import { Fab, FabGroup } from '@/components/common/Fab';
import { SectionCard } from '@/components/common/SectionCard';
import { SectionEditButton } from '@/components/common/SectionCardActions';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import SectionPlaceholder from '@/components/loading/SectionPlaceholder';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import {
  noop,
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import InfoRow from './MetricInfoRow';
import { NAV_LABELS } from './tabs';

/** The metric page, its Basic Information tab drawn with the metric's
 *  values pending. */
export default function MetricDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.metrics)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        actions={
          <FabGroup>
            <Can capability={Capability.Metric.CREATE}>
              <Fab icon={null} />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mb: 2 }}>
          {/* Tuning shows only for tunable metrics, which isn't known yet. */}
          <DetailTabNav
            tabs={[
              { key: 'basic', label: NAV_LABELS.basic },
              {
                key: 'linked-requirements',
                label: NAV_LABELS['linked-requirements'],
                icon: <LinkIcon />,
              },
            ]}
            activeIndex={0}
            onChange={noop}
            aria-label="Metric detail tabs"
          />
        </Box>
        <Stack spacing={3}>
          <SectionCard
            title="General Information"
            actions={<SectionEditButton onClick={noop} />}
          >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <InfoRow label="Name">
                <Typography>
                  <TextPlaceholder>{PLACEHOLDER_TEXT.title}</TextPlaceholder>
                </Typography>
              </InfoRow>
              <InfoRow label="Description">
                <Typography>
                  <TextPlaceholder>{PLACEHOLDER_TEXT.long}</TextPlaceholder>
                </Typography>
              </InfoRow>
            </Box>
          </SectionCard>
          <SectionPlaceholder title="Evaluation Process" editable />
        </Stack>
      </PageLayout>
    </SkeletonMode>
  );
}
