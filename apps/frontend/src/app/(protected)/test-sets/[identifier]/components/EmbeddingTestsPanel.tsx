'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
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
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import {
  buildEmbeddingChartColorConfig,
  EMBEDDING_COLOR_BY_OPTIONS,
  getEmbeddingChartColors,
  type EmbeddingColorBy,
} from '@/utils/embedding/embeddingColorBy';
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

const LIST_TAB = 0;
const CLUSTERS_TAB = 1;

interface EmbeddingTestsPanelProps {
  testSetId: string;
  sessionToken: string;
  testSetType?: string;
}

export default function EmbeddingTestsPanel({
  testSetId,
  sessionToken,
  testSetType,
}: EmbeddingTestsPanelProps) {
  const theme = useTheme();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(LIST_TAB);
  const clustersActive = activeTab === CLUSTERS_TAB;

  const { graph, isLoading, isComputing, error, computeGraph } =
    useEmbeddingGraph(testSetId, sessionToken, { enabled: clustersActive });

  const [tests, setTests] = useState<TestDetail[]>([]);
  const [testsLoading, setTestsLoading] = useState(false);
  const [testsError, setTestsError] = useState<string | null>(null);
  const [chartHoveredId, setChartHoveredId] = useState<string | null>(null);
  const [listHoveredId, setListHoveredId] = useState<string | null>(null);
  const [listVisible, setListVisible] = useState(false);
  const [colorBy, setColorBy] = useState<EmbeddingColorBy>('cluster');
  const hoveredEntityId = listHoveredId ?? chartHoveredId;
  const itemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  const hasPoints = (graph?.points.length ?? 0) > 0;
  const showChart = hasPoints && !isComputing;

  useEffect(() => {
    setListVisible(false);
    setChartHoveredId(null);
    setListHoveredId(null);
  }, [graph?.computed_at]);

  useEffect(() => {
    if (!clustersActive) return;

    let cancelled = false;
    const PAGE_SIZE = 100;

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
  }, [clustersActive, sessionToken, testSetId]);

  const embeddingColors = useMemo(
    () => getEmbeddingChartColors(theme),
    [theme]
  );

  const colorConfig = useMemo(() => {
    if (!graph || graph.points.length === 0) return null;
    return buildEmbeddingChartColorConfig(
      graph,
      tests,
      colorBy,
      embeddingColors
    );
  }, [graph, tests, colorBy, embeddingColors]);

  const sortedTests = useMemo(() => {
    if (!graph || graph.points.length === 0) return tests;
    const pointMap = new Map(graph.points.map(p => [p.entity_id, p]));

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
  }, [tests, graph, colorBy]);

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
    <Card elevation={2} sx={{ mb: 4 }}>
      <Tabs
        value={activeTab}
        onChange={(_, tabIndex: number) => setActiveTab(tabIndex)}
        variant="fullWidth"
        aria-label="Tests view"
        sx={{
          minHeight: 64,
          bgcolor: 'action.hover',
          borderBottom: 1,
          borderColor: 'divider',
          '& .MuiTabs-indicator': {
            height: 3,
          },
          '& .MuiTab-root': {
            minHeight: 64,
            py: 2,
            fontSize: theme => theme.typography.body1.fontSize,
            fontWeight: 600,
            textTransform: 'none',
            color: 'text.secondary',
            gap: 1,
            '&.Mui-selected': {
              color: 'primary.main',
              bgcolor: 'background.paper',
            },
          },
        }}
      >
        <Tab
          label="List"
          icon={<ViewListIcon sx={{ fontSize: 26 }} />}
          iconPosition="start"
        />
        <Tab
          label="Clusters"
          icon={<BubbleChartOutlinedIcon sx={{ fontSize: 26 }} />}
          iconPosition="start"
        />
      </Tabs>

      <CardContent sx={{ pt: 2.5, overflow: 'visible' }}>
        {activeTab === LIST_TAB && (
          <Box role="tabpanel" sx={{ width: '100%', minHeight: 400 }}>
            <TestSetTestsGrid
              testSetId={testSetId}
              sessionToken={sessionToken}
              testSetType={testSetType}
              embedded
            />
          </Box>
        )}

        {activeTab === CLUSTERS_TAB && (
          <Box role="tabpanel">
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
                <Stack direction="row" alignItems="center" spacing={1}>
                  <BetaBadge />
                  {graph?.computed_at && (
                    <Typography variant="body2" color="text.secondary">
                      Last computed{' '}
                      {formatDistanceToNow(new Date(graph.computed_at), {
                        addSuffix: true,
                      })}
                    </Typography>
                  )}
                </Stack>
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
                {graph && hasPoints ? 'Recompute clusters' : 'Compute clusters'}
              </Button>
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
                border: 1,
                borderColor: 'divider',
                overflow: 'hidden',
                bgcolor: 'background.default',
              }}
            >
              <Box
                sx={{
                  height: '100%',
                  overflow: 'hidden',
                  position: 'relative',
                  pr: listVisible ? HOVER_LIST_WIDTH : 0,
                  transition: theme =>
                    theme.transitions.create('padding-right', {
                      duration: theme.transitions.duration.short,
                    }),
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

                {!isLoading && !isComputing && graph && !hasPoints && (
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
                      No embeddings available yet. Add tests with embeddings,
                      then compute clusters.
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
                      &quot;Compute clusters&quot; to generate a 2D projection
                      with automatic cluster labels.
                    </Alert>
                  </Box>
                )}

                {showChart && graph && colorConfig && (
                  <>
                    <EmbeddingAtlasView
                      graph={graph}
                      colorConfig={colorConfig}
                      highlightedEntityId={hoveredEntityId}
                      onPointSelect={handlePointSelect}
                      onPointHover={handlePointHover}
                    />
                    <EmbeddingColorLegend entries={colorConfig.legend} />
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
                  borderLeft: listVisible ? 1 : 0,
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
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
                    Tests{tests.length > 0 ? ` · ${tests.length}` : ''}
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
      </CardContent>
    </Card>
  );
}
