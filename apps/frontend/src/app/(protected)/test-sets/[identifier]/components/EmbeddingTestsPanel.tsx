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
  Stack,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { formatDistanceToNow } from 'date-fns';
import { BetaBadge } from '@/components/common/BetaBadge';
import { useEmbeddingGraph } from '@/hooks/useEmbeddingGraph';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

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
const LIST_WIDTH = '38%';

interface EmbeddingTestsPanelProps {
  testSetId: string;
  sessionToken: string;
}

export default function EmbeddingTestsPanel({
  testSetId,
  sessionToken,
}: EmbeddingTestsPanelProps) {
  const router = useRouter();
  const { graph, isLoading, isComputing, error, computeGraph } =
    useEmbeddingGraph(testSetId, sessionToken);
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [testsLoading, setTestsLoading] = useState(true);
  const [testsError, setTestsError] = useState<string | null>(null);
  const [chartHoveredId, setChartHoveredId] = useState<string | null>(null);
  const [listHoveredId, setListHoveredId] = useState<string | null>(null);
  const [listVisible, setListVisible] = useState(false);
  const hoveredEntityId = listHoveredId ?? chartHoveredId;
  const itemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  const hasPoints = (graph?.points.length ?? 0) > 0;
  const showChart = hasPoints && !isComputing;

  // Hide the list again when clusters are recomputed.
  useEffect(() => {
    setListVisible(false);
    setChartHoveredId(null);
    setListHoveredId(null);
  }, [graph?.computed_at]);

  useEffect(() => {
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
  }, [sessionToken, testSetId]);

  // Sort tests so that spatially close points are adjacent in the list.
  // Primary key: cluster_index (groups nearby tests together).
  // Secondary key: x coordinate (left-to-right sweep within each cluster).
  // Tests with no embedding point fall to the end.
  const sortedTests = useMemo(() => {
    if (!graph || graph.points.length === 0) return tests;
    const pointMap = new Map(graph.points.map(p => [p.entity_id, p]));
    return [...tests].sort((a, b) => {
      const pa = pointMap.get(a.id);
      const pb = pointMap.get(b.id);
      if (!pa && !pb) return 0;
      if (!pa) return 1;
      if (!pb) return -1;
      if (pa.cluster_index !== pb.cluster_index)
        return pa.cluster_index - pb.cluster_index;
      return pa.x - pb.x;
    });
  }, [tests, graph]);

  // Scroll the list when a chart point is hovered and the item is outside view.
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
      <CardContent>
        {/* Header */}
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={2}
          sx={{ mb: 2 }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="h6">Test Clusters</Typography>
            <BetaBadge />
          </Stack>
          <Stack direction="row" alignItems="center" spacing={2}>
            {graph?.computed_at && (
              <Typography variant="caption" color="text.secondary">
                Last computed,{' '}
                {formatDistanceToNow(new Date(graph.computed_at), {
                  addSuffix: true,
                })}
              </Typography>
            )}
            <Button
              variant="contained"
              size="small"
              startIcon={
                isComputing ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <AutoAwesomeOutlinedIcon />
                )
              }
              onClick={() => void computeGraph()}
              disabled={isLoading || isComputing}
            >
              {graph && hasPoints ? 'Recompute' : 'Compute'}
            </Button>
          </Stack>
        </Stack>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ height: PANEL_HEIGHT, position: 'relative' }}>
          {/* Embedding canvas */}
          <Box
            sx={{
              height: '100%',
              overflow: 'hidden',
              position: 'relative',
              pr: listVisible ? LIST_WIDTH : 0,
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
                }}
              >
                <Alert severity="info" icon={<RefreshIcon />}>
                  No embeddings available yet. Add tests with embeddings, then
                  compute clusters.
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
                }}
              >
                <Alert severity="info">
                  Visualize how tests cluster in embedding space. Click
                  &quot;Compute&quot; to generate a 2D projection with automatic
                  cluster labels.
                </Alert>
              </Box>
            )}

            {showChart && graph && (
              <EmbeddingAtlasView
                graph={graph}
                highlightedEntityId={hoveredEntityId}
                onPointSelect={handlePointSelect}
                onPointHover={handlePointHover}
              />
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
              width: listVisible ? LIST_WIDTH : 0,
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
                minWidth: LIST_WIDTH,
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
                <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}>
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
                  const content = test.prompt?.content ?? '';
                  return (
                    <Box
                      key={test.id}
                      ref={el => setItemRef(test.id, el as HTMLElement | null)}
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
                        transition: 'background-color 0.1s, border-color 0.1s',
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
      </CardContent>
    </Card>
  );
}
