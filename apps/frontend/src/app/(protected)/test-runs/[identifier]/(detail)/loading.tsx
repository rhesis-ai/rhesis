'use client';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useSearchParams } from 'next/navigation';
import { Can } from '@/components/common/Can';
import DetailTabNav from '@/components/common/DetailTabNav';
import { Fab, FabGroup } from '@/components/common/Fab';
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
import KpiCard from '../components/summary/KpiCard';
import { TAB_KEYS, TAB_LABELS, tabIndexFromKey } from '../utils/tab-key';

const KPI_TITLES = ['Pass rate', 'Tests executed', 'Verdicts', 'Cost'];
const REQUIREMENT_ROWS = ['row-1', 'row-2', 'row-3', 'row-4'];

/** The run's header (TestRunMetadata's line, without the status pill). */
function MetadataPlaceholder() {
  return (
    <Typography
      variant="body2"
      sx={{ color: theme => theme.palette.greyscale.subtitle }}
    >
      created by: <TextPlaceholder>{PLACEHOLDER_TEXT.person}</TextPlaceholder>
      <Box component="span" sx={{ mx: 2 }}>
        |
      </Box>
      created on: <TextPlaceholder>{PLACEHOLDER_TEXT.date}</TextPlaceholder>
    </Typography>
  );
}

/** The Summary tab: the KPI cards, then the requirements table's frame. */
function SummaryPlaceholder() {
  return (
    <Stack spacing={3}>
      <Box sx={{ mb: 4 }}>
        <Grid container spacing={3}>
          {KPI_TITLES.map(title => (
            <Grid key={title} size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiCard title={title} value={PLACEHOLDER_TEXT.count} />
            </Grid>
          ))}
        </Grid>
      </Box>
      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Typography
            variant="subtitle1"
            fontWeight={600}
            sx={{ color: theme => theme.palette.greyscale.title }}
          >
            Requirements performance
          </Typography>
        </Box>
        {REQUIREMENT_ROWS.map(key => (
          <Box
            key={key}
            sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider' }}
          >
            <Typography variant="body2">
              <TextPlaceholder>{PLACEHOLDER_TEXT.long}</TextPlaceholder>
            </Typography>
          </Box>
        ))}
      </Paper>
    </Stack>
  );
}

/** The test run page's header and tabs, with what waits for the run drawn
 *  as placeholders. */
export default function TestRunDetailLoading() {
  const searchParams = useSearchParams();
  const tab = searchParams.get('tab');
  // Same resolution TestRunMainView runs, ?selectedresult= included.
  const activeTab = tabIndexFromKey(
    tab,
    Boolean(searchParams.get('selectedresult')) && !tab
  );

  return (
    <SkeletonMode>
      <PageLayout
        breadcrumbs={[directoryCrumb(PAGE_HEADERS.testRuns)]}
        pendingCrumbs={1}
        title={<PageTitlePlaceholder />}
        metadata={<MetadataPlaceholder />}
        actions={
          <FabGroup>
            <Can capability={Capability.Architect.CREATE}>
              <Fab icon={null} />
            </Can>
            <Fab icon={null} />
            <Fab icon={null} />
            <Fab icon={null} />
          </FabGroup>
        }
      >
        {/* Annotations' count badge shows only once there are annotations,
            so it has no placeholder. */}
        <DetailTabNav
          tabs={TAB_KEYS.map(key => ({ key, label: TAB_LABELS[key] }))}
          activeIndex={activeTab}
          onChange={noop}
          aria-label="Test run detail tabs"
        />
        {/* TestRunMainView's TabPanel inset. */}
        <Box sx={{ pt: 3 }}>
          {TAB_KEYS[activeTab] === 'summary' ? (
            <SummaryPlaceholder />
          ) : (
            <SectionPlaceholder />
          )}
        </Box>
      </PageLayout>
    </SkeletonMode>
  );
}
