'use client';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import DownloadIcon from '@mui/icons-material/Download';
import { Can } from '@/components/common/Can';
import {
  SectionEditButton,
  sectionEditButtonSx,
} from '@/components/common/SectionCardActions';
import {
  PageLayout,
  PageTitlePlaceholder,
} from '@/components/layout/PageLayout';
import { SkeletonMode, SkeletonSlot } from '@/components/loading/SkeletonMode';
import {
  noop,
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { Capability } from '@/constants/capabilities';
import { directoryCrumb, PAGE_HEADERS } from '@/constants/page-headers';
import {
  InfoRow,
  SectionHeader,
  sourcePaperSx,
} from './components/SourceSectionParts';

/** The source page's Source Information card, its values pending. Size and
 *  type show only for some sources, so they have no placeholders. */
export default function KnowledgeDetailLoading() {
  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.knowledge)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
      >
        <Stack direction="column" spacing={3}>
          <Paper sx={sourcePaperSx}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 3,
                pb: 2,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <SectionHeader title="Source Information" />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <SkeletonSlot>
                  <Button
                    startIcon={<DownloadIcon />}
                    variant="outlined"
                    size="small"
                    sx={sectionEditButtonSx}
                  >
                    Download
                  </Button>
                </SkeletonSlot>
                <Can capability={Capability.Source.UPDATE}>
                  <SectionEditButton onClick={noop} />
                </Can>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <InfoRow label="Title">
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
            <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 3, mt: 3 }} />
            <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap', mb: 3 }}>
              <InfoRow label="Added by">
                <Typography variant="body1">
                  <TextPlaceholder>{PLACEHOLDER_TEXT.person}</TextPlaceholder>
                </Typography>
              </InfoRow>
              <InfoRow label="Added on">
                <Typography variant="body1">
                  <TextPlaceholder>{PLACEHOLDER_TEXT.date}</TextPlaceholder>
                </Typography>
              </InfoRow>
            </Box>
          </Paper>
        </Stack>
      </PageLayout>
    </SkeletonMode>
  );
}
