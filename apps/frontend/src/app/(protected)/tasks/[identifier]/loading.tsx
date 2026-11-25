'use client';

import Grid from '@mui/material/Grid';
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
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import { noop, PLACEHOLDER_TEXT } from '@/components/loading/TextPlaceholder';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import { TAB_KEYS, TAB_LABELS } from './components/tabs';

/** TaskDetailsCard's read-only fields and their widths. */
const TASK_FIELDS = [
  { label: 'Title', size: { xs: 12 } },
  { label: 'Description', size: { xs: 12 } },
  { label: 'Status', size: { xs: 12, sm: 6 } },
  { label: 'Priority', size: { xs: 12, sm: 6 } },
  { label: 'Assignee', size: { xs: 12, sm: 6 } },
];

/** The task page, its Basic Information tab drawn with the task's values
 *  pending. */
export default function TaskDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.tasks)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<CreatedMetadataPlaceholder />}
        // CreateJiraIssueButton: create or open the linked issue.
        actions={
          <FabGroup>
            <Fab icon={null} />
          </FabGroup>
        }
      >
        <DetailTabNav
          tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
          activeIndex={0}
          onChange={noop}
          aria-label="Task detail tabs"
        />
        <DetailTabPanel value={0} index={0} prefix="task-detail">
          <SectionCard
            title="Task details"
            actions={<SectionEditButton onClick={noop} />}
          >
            <Grid container columnSpacing={4} rowSpacing={6}>
              {TASK_FIELDS.map(({ label, size }) => (
                <Grid key={label} size={size}>
                  <ViewField label={label} value={PLACEHOLDER_TEXT.value} />
                </Grid>
              ))}
            </Grid>
          </SectionCard>
        </DetailTabPanel>
      </PageLayout>
    </SkeletonMode>
  );
}
