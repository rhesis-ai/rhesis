'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import type { GridFilterModel } from '@mui/x-data-grid';
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import type { SelectChangeEvent } from '@mui/material/Select';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import ViewListIcon from '@mui/icons-material/ViewList';
import BubbleChartOutlinedIcon from '@mui/icons-material/BubbleChartOutlined';
import { formatDistanceToNow } from 'date-fns';
import { BetaBadge } from '@/components/common/BetaBadge';
import { useEmbeddingGraph } from '@/hooks/useEmbeddingGraph';
import { getTestDisplayContent } from '@/app/(protected)/tests/components/test-grid-helpers';
import TestsQuickFilterField from '@/app/(protected)/tests/components/TestsQuickFilterField';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import { filterScatter2DGraph } from '@/utils/embedding/filterScatter2DGraph';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import {
  buildEmbeddingChartColorConfig,
  EMBEDDING_COLOR_BY_OPTIONS,
  getEmbeddingChartColors,
  type EmbeddingColorBy,
} from '@/utils/embedding/embeddingColorBy';
import { getEmbeddingViewSurfaceBg } from '@/utils/embedding/embeddingViewSurface';
import TestSetTestsGrid from './TestSetTestsGrid';
import EmbeddingColorLegend from './EmbeddingColorLegend';

const EmbeddingAtlasView = dynamic(() => import('./EmbeddingAtlasView'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
      }}
    >
      <CircularProgress size={32} />
    </Box>
  ),
});

const PANEL_HEIGHT = 560;
const HOVER_LIST_WIDTH = '38%';

const LIST_VIEW_TAB = 0;
const CLUSTER_VIEW_TAB = 1;

interface EmbeddingTestsPanelProps {
  testSetId: string;
  sessionToken: string;
  testSetType?: string;
  onTotalCountChange?: (count: number) => void;
}

export default function EmbeddingTestsPanel({
  testSetId,
  sessionToken,
  testSetType,
  onTotalCountChange,
}: EmbeddingTestsPanelProps) {
  const theme = useTheme();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(LIST_VIEW_TAB);
  const clustersActive = activeTab === CLUSTER_VIEW_TAB;

  const { graph, isLoading, isComputing, error, computeGraph } =
    useEmbeddingGraph(testSetId, sessionToken, { enabled: clustersActive });

  const [tests, setTests] = useState<TestDetail[]>([]);
  const [testsLoading, setTestsLoading] = useState(false);
  const [testsError, setTestsError] = useState<string | null>(null);
  const [chartHoveredId, setChartHoveredId] = useState<string | null>(null);
  const [listHoveredId, setListHoveredId] = useState<string | null>(null);
  const [listVisible, setListVisible] = useState(false);
  const [colorBy, setColorBy] = useState<EmbeddingColorBy>('cluster');
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const handleFilterModelChange = useCallback((model: GridFilterModel) => {
    setFilterModel(model);
    setChartHoveredId(null);
    setListHoveredId(null);
  }, []);
  const hoveredEntityId = listHoveredId ?? chartHoveredId;
  const itemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setListVisible(false);
    setChartHoveredId(null);
    setListHoveredId(null);
  }, [graph?.computed_at]);

  useEffect(() => {
    if (!clustersActive) return;

    let cancelled = false;
    const PAGE_SIZE = 100;
    const filterString = combineTestFiltersToOData(filterModel);

    async function fetchAll() {
      setTestsLoading(true);
      setTestsError(null);
      const client = new ApiClientFactory(sessionToken).getTestSetsClient();
      const accumulated: TestDetail[] = [];
      let skip = 0;

      try {
        while (true) {
          const res = await client.getTestSetTests(testSetId, {
            skip,
            limit: PAGE_SIZE,
            ...(filterString && { $filter: filterString }),
          });
          if (cancelled) return;
          accumulated.push(...res.data);
          if (
            accumulated.length >= res.pagination.totalCount ||
            res.data.length < PAGE_SIZE
          )
            break;
          skip += PAGE_SIZE;
        }
        setTests(accumulated);
      } catch (err) {
        if (!cancelled) {
          console.error('[EmbeddingTestsPanel] failed to load tests', err);
          setTestsError(
            err instanceof Error ? err.message : 'Failed to load tests'
          );
        }
      } finally {
        if (!cancelled) setTestsLoading(false);
      }
    }

    void fetchAll();
    return () => {
      cancelled = true;
    };
  }, [clustersActive, sessionToken, testSetId, filterModel]);

  const embeddingColors = useMemo(
    () => getEmbeddingChartColors(theme),
    [theme]
  );

  const filteredEntityIds = useMemo((): Set<string> => {
    return new Set(tests.map(t => String(t.id)));
  }, [tests]);

  const displayGraph = useMemo(() => {
    if (!graph) return null;
    const needsFilter = graph.points.some(
      p => !filteredEntityIds.has(p.entity_id)
    );
    if (!needsFilter) return graph;
    return filterScatter2DGraph(graph, filteredEntityIds);
  }, [graph, filteredEntityIds]);

  const colorConfig = useMemo(() => {
    if (!displayGraph || displayGraph.points.length === 0) return null;
    return buildEmbeddingChartColorConfig(
      displayGraph,
      tests,
      colorBy,
      embeddingColors
    );
  }, [displayGraph, tests, colorBy, embeddingColors]);

  const sortedTests = useMemo(() => {
    if (!displayGraph || displayGraph.points.length === 0) return tests;
    const pointMap = new Map(displayGraph.points.map(p => [p.entity_id, p]));

    const metadataKey = (test: TestDetail): string => {
      switch (colorBy) {
        case 'behavior':
          return test.behavior?.name ?? '';
        case 'category':
          return test.category?.name ?? '';
        case 'topic':
          return test.topic?.name ?? '';
        default:
          return '';
      }
    };

    return [...tests].sort((a, b) => {
      const pa = pointMap.get(a.id);
      const pb = pointMap.get(b.id);
      if (!pa && !pb) return 0;
      if (!pa) return 1;
      if (!pb) return -1;

      if (colorBy !== 'cluster') {
        const keyCmp = metadataKey(a).localeCompare(metadataKey(b));
        if (keyCmp !== 0) return keyCmp;
      } else if (pa.cluster_index !== pb.cluster_index) {
        return pa.cluster_index - pb.cluster_index;
      }
      return pa.x - pb.x;
    });
  }, [tests, displayGraph, colorBy]);

  const hasPoints = (displayGraph?.points.length ?? 0) > 0;
  const showChart = hasPoints && !isComputing;
  const hasActiveFilters =
    filterModel.items.length > 0 &&
    !testsLoading &&
    graph != null &&
    graph.points.length > 0 &&
    !hasPoints;

  const handleColorByChange = useCallback((event: SelectChangeEvent) => {
    setColorBy(event.target.value as EmbeddingColorBy);
  }, []);

  useEffect(() => {
    if (!listVisible || !hoveredEntityId || !listRef.current) return;
    const el = itemRefs.current.get(hoveredEntityId);
    if (!el) return;
    const container = listRef.current;
    const elTop = el.offsetTop - container.offsetTop;
    const elBottom = elTop + el.offsetHeight;
    const visible = container.scrollTop;
    const visibleBottom = visible + container.clientHeight;
    if (elTop < visible || elBottom > visibleBottom) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [hoveredEntityId, listVisible]);

  const setItemRef = useCallback((id: string, el: HTMLElement | null) => {
    if (el) itemRefs.current.set(id, el);
    else itemRefs.current.delete(id);
  }, []);

  const handlePointHover = useCallback((entityId: string | null) => {
    setChartHoveredId(entityId);
    if (entityId) setListVisible(true);
  }, []);

  const handlePointSelect = useCallback(
    (entityId: string) => router.push(`/tests/${entityId}`),
    [router]
  );

  return (
    <Card
      elevation={2}
      sx={{
        mb: 4,
        overflow: 'visible',
        bgcolor: theme =>
          activeTab === CLUSTER_VIEW_TAB && theme.palette.mode === 'dark'
            ? getEmbeddingViewSurfaceBg(theme)
            : undefined,
      }}
    >
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={(_, tabIndex: number) => setActiveTab(tabIndex)}
          aria-label="Tests view"
        >
          <Tab
            label="List View"
            icon={<ViewListIcon fontSize="small" />}
            iconPosition="start"
          />
          <Tab
            label="Cluster View"
            icon={<BubbleChartOutlinedIcon fontSize="small" />}
            iconPosition="start"
          />
        </Tabs>
      </Box>

      {activeTab === LIST_VIEW_TAB && (
        <Box sx={{ p: 2.5, width: '100%', minHeight: 400 }}>
          <TestSetTestsGrid
            testSetId={testSetId}
            sessionToken={sessionToken}
            testSetType={testSetType}
            embedded
            onTotalCountChange={onTotalCountChange}
          />
        </Box>
      )}

      {activeTab === CLUSTER_VIEW_TAB && (
        <Box
          sx={{
            p: 2.5,
            bgcolor: theme => getEmbeddingViewSurfaceBg(theme),
          }}
        >
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            spacing={2}
            sx={{ mb: 2 }}
            flexWrap="wrap"
            useFlexGap
          >
            <Stack
              direction="row"
              alignItems="center"
              spacing={2}
              flexWrap="wrap"
              useFlexGap
            >
              <BetaBadge />
              {showChart && (
                <FormControl size="small" sx={{ minWidth: 140 }}>
                  <InputLabel id="embedding-color-by-label">
                    Color by
                  </InputLabel>
                  <Select
                    labelId="embedding-color-by-label"
                    label="Color by"
                    value={colorBy}
                    onChange={handleColorByChange}
                  >
                    {EMBEDDING_COLOR_BY_OPTIONS.map(opt => (
                      <MenuItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            </Stack>
            <Stack
              direction="row"
              alignItems="center"
              spacing={2}
              flexWrap="wrap"
              useFlexGap
            >
              <TestsQuickFilterField
                filterModel={filterModel}
                onFilterModelChange={handleFilterModelChange}
              />
              {graph?.computed_at && (
                <Typography variant="body2" color="text.secondary">
                  Last computed{' '}
                  {formatDistanceToNow(new Date(graph.computed_at), {
                    addSuffix: true,
                  })}
                </Typography>
              )}
              <Button
                variant="contained"
                startIcon={
                  isComputing ? (
                    <CircularProgress size={18} color="inherit" />
                  ) : (
                    <AutoAwesomeOutlinedIcon />
                  )
                }
                onClick={() => void computeGraph()}
                disabled={isLoading || isComputing}
              >
                {graph && graph.points.length > 0
                  ? 'Recompute clusters'
                  : 'Compute clusters'}
              </Button>
            </Stack>
          </Stack>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box
            sx={{
              height: PANEL_HEIGHT,
              position: 'relative',
              borderRadius: theme => theme.shape.borderRadius,
              border: theme => (theme.palette.mode === 'dark' ? 0 : 1),
              borderStyle: 'solid',
              borderColor: 'divider',
              overflow: 'hidden',
              bgcolor: theme => getEmbeddingViewSurfaceBg(theme),
            }}
          >
            <Box
              sx={{
                height: '100%',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              {isLoading && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                  }}
                >
                  <CircularProgress />
                </Box>
              )}

              {!isLoading && isComputing && (
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    gap: 2,
                  }}
                >
                  <CircularProgress />
                  <Typography variant="body2" color="text.secondary">
                    Computing clusters and labels…
                  </Typography>
                </Box>
              )}

              {!isLoading &&
                !isComputing &&
                graph &&
                graph.points.length === 0 && (
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      p: 2,
                    }}
                  >
                    <Alert severity="info" icon={<RefreshIcon />}>
                      No tests could be embedded (empty content or missing
                      embedding model). Add content to tests or configure an
                      embedding model, then compute clusters again.
                    </Alert>
                  </Box>
                )}

              {!isLoading && !isComputing && !graph && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    p: 2,
                  }}
                >
                  <Alert severity="info">
                    Visualize how tests cluster in embedding space. Click
                    &quot;Compute clusters&quot; to generate embeddings for
                    tests that need them, then build a 2D projection with
                    automatic cluster labels.
                  </Alert>
                </Box>
              )}

              {hasActiveFilters && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    p: 2,
                  }}
                >
                  <Alert severity="info">
                    No tests match the current search or filters. Adjust filters
                    or clear search to see clusters.
                  </Alert>
                </Box>
              )}

              {showChart &&
                displayGraph &&
                colorConfig &&
                !hasActiveFilters && (
                  <>
                    <EmbeddingAtlasView
                      graph={displayGraph}
                      colorConfig={colorConfig}
                      highlightedEntityId={hoveredEntityId}
                      onPointSelect={handlePointSelect}
                      onPointHover={handlePointHover}
                    />
                    {colorBy !== 'cluster' && (
                      <EmbeddingColorLegend entries={colorConfig.legend} />
                    )}
                  </>
                )}
            </Box>

            {/* Tests list — slides in when hovering chart points */}
            <Box
              onMouseLeave={() => setListHoveredId(null)}
              sx={{
                position: 'absolute',
                top: 0,
                right: 0,
                bottom: 0,
                width: listVisible ? HOVER_LIST_WIDTH : 0,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                borderLeft: listVisible
                  ? theme => (theme.palette.mode === 'dark' ? 0 : 1)
                  : 0,
                borderColor: 'divider',
                bgcolor: theme => getEmbeddingViewSurfaceBg(theme),
                zIndex: 1,
                pointerEvents: listVisible ? 'auto' : 'none',
                transition: theme =>
                  theme.transitions.create('width', {
                    duration: theme.transitions.duration.short,
                  }),
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  height: '100%',
                  minWidth: HOVER_LIST_WIDTH,
                  pl: 2,
                  pr: 1,
                }}
              >
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  sx={{ py: 1, flexShrink: 0 }}
                >
                  Tests
                  {tests.length > 0
                    ? ` · ${tests.length}${graph && tests.length < graph.points.length ? ` of ${graph.points.length}` : ''}`
                    : ''}
                </Typography>

                {testsLoading && (
                  <Box
                    sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}
                  >
                    <CircularProgress size={24} />
                  </Box>
                )}

                {testsError && (
                  <Alert severity="error" sx={{ mx: 0 }}>
                    {testsError}
                  </Alert>
                )}

                <Box ref={listRef} sx={{ overflow: 'auto', flex: 1 }}>
                  {sortedTests.map(test => {
                    const isHighlighted = hoveredEntityId === test.id;
                    const content = getTestDisplayContent(test);
                    return (
                      <Box
                        key={test.id}
                        ref={el =>
                          setItemRef(test.id, el as HTMLElement | null)
                        }
                        onMouseEnter={() => setListHoveredId(test.id)}
                        onClick={() => router.push(`/tests/${test.id}`)}
                        sx={{
                          p: '8px 10px',
                          mb: '3px',
                          borderRadius: theme => theme.shape.borderRadius,
                          cursor: 'pointer',
                          border: '1px solid',
                          borderColor: isHighlighted
                            ? 'primary.main'
                            : 'transparent',
                          bgcolor: isHighlighted
                            ? 'action.selected'
                            : 'transparent',
                          transition:
                            'background-color 0.1s, border-color 0.1s',
                          '&:hover': {
                            bgcolor: isHighlighted
                              ? 'action.selected'
                              : 'action.hover',
                          },
                        }}
                      >
                        <Typography
                          variant="body2"
                          sx={{
                            fontSize: 12,
                            lineHeight: 1.4,
                            mb: 0.5,
                            color: 'text.primary',
                          }}
                        >
                          {content.length > 120
                            ? `${content.slice(0, 120)}…`
                            : content}
                        </Typography>
                        <Stack direction="row" spacing={0.5} flexWrap="wrap">
                          {test.behavior?.name && (
                            <Chip
                              label={test.behavior.name}
                              size="small"
                              variant="outlined"
                              sx={{ height: 18, fontSize: 10 }}
                            />
                          )}
                          {test.category?.name && (
                            <Chip
                              label={test.category.name}
                              size="small"
                              variant="outlined"
                              sx={{ height: 18, fontSize: 10 }}
                            />
                          )}
                          {test.topic?.name && (
                            <Chip
                              label={test.topic.name}
                              size="small"
                              variant="outlined"
                              sx={{ height: 18, fontSize: 10 }}
                            />
                          )}
                        </Stack>
                      </Box>
                    );
                  })}
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>
      )}
    </Card>
  );
}
