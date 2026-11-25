'use client';

import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import LinkIcon from '@mui/icons-material/Link';
import { useCan } from '@/components/common/Can';
import { CreatedMetadataPlaceholder } from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import GeneralInfoCard from '@/components/common/GeneralInfoCard';
import GridBadge from '@/components/common/GridBadge';
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
import { NAV_LABELS, REQUIREMENT_TAB_KEYS } from './components/tabs';

const BASIC_FIELDS = ['Name', 'Description', 'Impact', 'Parent requirement'];

/** The requirement page, its Basic Information tab drawn with the
 *  requirement's values pending. A parent requirement adds a crumb, which
 *  isn't known yet, so the trail draws the usual one. */
export default function RequirementDetailLoading() {
  const canEdit = useCan(Capability.Requirement.UPDATE);
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.requirements)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        // RequirementSuggestionsFab.
        actions={
          <FabGroup>
            <Fab icon={null} />
          </FabGroup>
        }
      >
        <Box sx={{ flexGrow: 1 }}>
          {/* Every tab after Basic Information is a link list with a count. */}
          <DetailTabNav
            tabs={REQUIREMENT_TAB_KEYS.map(key => ({
              key,
              label: NAV_LABELS[key],
              ...(key !== 'basic' && {
                icon: <LinkIcon />,
                badge: <GridBadge label={PLACEHOLDER_TEXT.count} />,
              }),
            }))}
            activeIndex={0}
            onChange={noop}
            aria-label="Requirement detail tabs"
          />
          <DetailTabPanel value={0} index={0} prefix="requirement-detail">
            <Box sx={{ mb: 3 }}>
              <GeneralInfoCard onEdit={canEdit ? noop : undefined}>
                <Stack spacing={3}>
                  {BASIC_FIELDS.map(label => (
                    <ViewField
                      key={label}
                      label={label}
                      value={PLACEHOLDER_TEXT.value}
                    />
                  ))}
                </Stack>
              </GeneralInfoCard>
            </Box>
            <SectionPlaceholder
              title="Sources"
              subtitle="Where this rule comes from"
            />
          </DetailTabPanel>
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
