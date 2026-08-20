'use client';

import * as React from 'react';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import TablePagination from '@mui/material/TablePagination';
import GridToolbar, {
  PrimarySegmentedPills,
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { useRouter, useSearchParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import SelectRequirementsDialog from '@/components/common/SelectRequirementsDialog';
import MetricFilterDrawer from './MetricFilterDrawer';
import { PageLayout } from '@/components/layout/PageLayout';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { InsertChartIcon } from '@/components/icons';
import MetricCard from './MetricCard';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import {
  OWASP_METRIC_FILTER_VALUE,
  OWASP_METRIC_TAG_NAME,
} from '@/utils/odata-filter';
export interface FilterState {
  search: string;
  backend: string[];
  type: string[];
  scoreType: string[];
  metricScope: string[];
  requirement: string;
}

export interface FilterOptions {
  backend: { type_value: string }[];
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
  requirement: { id: string; name: string }[];
}

interface MetricsDirectoryTabProps {
  organizationId: UUID;
  metrics: MetricDetail[];
  totalCount: number;
  page: number;
  rowsPerPage: number;
  onPageChange: (page: number) => void;
  onRowsPerPageChange: (size: number) => void;
  onRefresh: () => void;
  filters: FilterState;
  filterOptions: FilterOptions;
  isLoading: boolean;
  error: string | null;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  setMetrics: React.Dispatch<React.SetStateAction<MetricDetail[]>>;
  assignMode?: boolean;
}

// Add type guard function
function isValidMetricType(
  type: string | undefined
): type is 'custom-prompt' | 'api-call' | 'custom-code' | 'grading' {
  return (
    type === 'custom-prompt' ||
    type === 'api-call' ||
    type === 'custom-code' ||
    type === 'grading'
  );
}

// Read off the metric rather than a separately-fetched requirements list: while
// such a fetch is in flight every metric looks unassigned, which blanks the
// badges and offers delete on metrics that are in use.
function getAssignedRequirementNames(metric: MetricDetail): string[] {
  return (metric.requirements ?? [])
    .map(requirement => requirement.name ?? '')
    .filter(name => name.trim() !== '');
}

export default function MetricsDirectoryTab({
  organizationId: _organizationId,
  metrics,
  totalCount,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
  onRefresh,
  filters,
  filterOptions,
  isLoading,
  error,
  setFilters,
  setMetrics,
  assignMode = false,
}: MetricsDirectoryTabProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const { status } = useSession();
  const canCreate = useCan(Capability.Metric.CREATE);
  const canDelete = useCan(Capability.Metric.DELETE);

  // Dialog state
  const [assignDialogOpen, setAssignDialogOpen] = React.useState(false);
  const [selectedMetric, setSelectedMetric] =
    React.useState<MetricDetail | null>(null);
  const [fabAnchorEl, setFabAnchorEl] = React.useState<null | HTMLElement>(
    null
  );
  const fabMenuOpen = Boolean(fabAnchorEl);
  const [deleteMetricDialogOpen, setDeleteMetricDialogOpen] =
    React.useState(false);
  const [metricToDeleteCompletely, setMetricToDeleteCompletely] =
    React.useState<{ id: string; name: string } | null>(null);
  const [isDeletingMetric, setIsDeletingMetric] = React.useState(false);

  // Advanced filters drawer state
  const [filterDrawerOpen, setFilterDrawerOpen] = React.useState(false);

  // Filter handlers — parent resets page to 0 when filters change
  const handleFilterChange = (
    filterType: keyof FilterState,
    value: string | string[]
  ) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value,
    }));
  };

  // Count active advanced filters
  const requirementStr =
    typeof filters.requirement === 'string' ? filters.requirement : '';
  const activeAdvancedFilterCount =
    filters.type.length +
    filters.scoreType.length +
    filters.metricScope.length +
    (requirementStr.trim() !== '' ? 1 : 0);

  // True empty = server returned zero results and no filters are active
  const isTrueEmpty =
    totalCount === 0 &&
    !filters.search &&
    filters.backend.length === 0 &&
    activeAdvancedFilterCount === 0;

  const handleAssignMetricToRequirement = async (
    requirementId: string,
    metricId: string,
    requirementName: string
  ) => {
    try {
      const metricClient = new MetricsClient();

      await metricClient.addRequirementToMetric(
        metricId as UUID,
        requirementId as UUID
      );

      setMetrics(prevMetrics =>
        prevMetrics.map(metric => {
          if (metric.id !== metricId) return metric;
          const currentRequirements = metric.requirements ?? [];
          if (currentRequirements.some(r => r.id === requirementId))
            return metric;
          return {
            ...metric,
            requirements: [
              ...currentRequirements,
              { id: requirementId as UUID, name: requirementName },
            ],
          };
        })
      );

      notifications.show('Successfully assigned metric to requirement', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to assign metric to requirement', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    }
  };

  const handleAssignMetric = (requirementId: UUID, requirementName: string) => {
    if (selectedMetric) {
      handleAssignMetricToRequirement(
        requirementId as string,
        selectedMetric.id,
        requirementName
      );
    }
    setAssignDialogOpen(false);
    setSelectedMetric(null);

    // Clear assignMode param from URL if present
    if (assignMode) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('assignMode');
      router.replace(`/metrics?${params.toString()}`, { scroll: false });
    }
  };

  // Function to delete a metric
  const handleDeleteMetric = async (metricId: string, metricName: string) => {
    setMetricToDeleteCompletely({ id: metricId, name: metricName });
    setDeleteMetricDialogOpen(true);
  };

  const handleConfirmDeleteMetric = async () => {
    if (!isAuthenticated(status) || !metricToDeleteCompletely) return;

    try {
      setIsDeletingMetric(true);
      const metricClient = new MetricsClient();
      await metricClient.deleteMetric(metricToDeleteCompletely.id as UUID);

      onRefresh();

      notifications.show('Metric deleted successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (_err) {
      notifications.show('Failed to delete metric', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeletingMetric(false);
      setDeleteMetricDialogOpen(false);
      setMetricToDeleteCompletely(null);
    }
  };

  const handleCancelDeleteMetric = () => {
    setDeleteMetricDialogOpen(false);
    setMetricToDeleteCompletely(null);
  };

  // First load — no data at all yet, show a full-page spinner
  const isInitialLoad = isLoading && metrics.length === 0 && totalCount === 0;

  if (isInitialLoad) {
    return (
      <PageLayout title="Metrics" breadcrumbs={[]}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            p: 4,
            minHeight: theme => theme.spacing(50),
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={24} />
            <Typography>Loading metrics directory...</Typography>
          </Box>
        </Box>
      </PageLayout>
    );
  }

  if (error && metrics.length === 0) {
    return (
      <PageLayout title="Metrics" breadcrumbs={[]}>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <Typography color="error">{error}</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Metrics"
      description="Metrics are quantifiable measurements that evaluate requirements and determine if requirements are met."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Metric.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create metric"
              aria-label="Create metric"
              onClick={e => setFabAnchorEl(e.currentTarget)}
            />
          </Can>
          <Menu
            anchorEl={fabAnchorEl}
            open={fabMenuOpen}
            onClose={() => setFabAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem
              onClick={() => {
                setFabAnchorEl(null);
                router.push('/metrics/new?type=custom-prompt');
              }}
            >
              LLM judge
            </MenuItem>
            <MenuItem
              onClick={() => {
                setFabAnchorEl(null);
                window.open(
                  'https://docs.rhesis.ai/docs/metrics/code-metrics',
                  '_blank',
                  'noopener,noreferrer'
                );
              }}
            >
              Code Evaluation
            </MenuItem>
          </Menu>
        </FabGroup>
      }
    >
      {isTrueEmpty ? (
        <EntityEmptyState
          card
          icon={InsertChartIcon}
          title="No metrics yet"
          description="Create your first metric to measure requirements and evaluate whether your AI applications meet requirements."
          actionLabel={canCreate ? 'Create metric' : undefined}
          onAction={
            canCreate
              ? () => router.push('/metrics/new?type=custom-prompt')
              : undefined
          }
          enrichment={getEntityEmptyStateEnrichment('metrics')}
        />
      ) : (
        <>
          <GridToolbar
            searchQuery={filters.search}
            onSearchChange={value => handleFilterChange('search', value)}
            searchPlaceholder="Search metrics..."
            onFilterClick={() => setFilterDrawerOpen(true)}
            hasActiveFilters={activeAdvancedFilterCount > 0}
            activeFilterCount={activeAdvancedFilterCount}
            {...directoryToolbarProps}
            middleContent={
              <PrimarySegmentedPills
                mode="multi"
                tabs={[
                  { value: '', label: 'All' },
                  ...filterOptions.backend.map(o => ({
                    value: o.type_value.toLowerCase(),
                    label: o.type_value,
                  })),
                  {
                    value: OWASP_METRIC_FILTER_VALUE,
                    label: OWASP_METRIC_TAG_NAME,
                  },
                ]}
                selectedValues={filters.backend}
                onMultiChange={values => handleFilterChange('backend', values)}
                clearValue=""
              />
            }
          />

          {/* Advanced Filters Drawer */}
          <MetricFilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            filters={{
              type: filters.type,
              scoreType: filters.scoreType,
              metricScope: filters.metricScope,
              requirement:
                typeof filters.requirement === 'string'
                  ? filters.requirement
                  : '',
            }}
            filterOptions={{
              type: filterOptions.type,
              scoreType: filterOptions.scoreType,
              metricScope: filterOptions.metricScope,
              requirement: filterOptions.requirement,
            }}
            onApply={drawerFilters => {
              setFilters(prev => ({
                ...prev,
                type: drawerFilters.type,
                scoreType: drawerFilters.scoreType,
                metricScope: drawerFilters.metricScope,
                requirement: drawerFilters.requirement,
              }));
            }}
          />

          {/* Subtle loading indicator for subsequent fetches — always
              mounted so its height never shifts the grid below */}
          <LinearProgress
            sx={{
              mb: 1,
              borderRadius: theme => theme.shape.borderRadius,
              visibility: isLoading ? 'visible' : 'hidden',
            }}
          />

          {/* Metrics grid */}
          <Box
            sx={theme => ({
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: '1fr 1fr',
                md: 'repeat(3, 1fr)',
              },
              gap: theme.spacing(3),
              mb: 4,
            })}
          >
            {metrics.map(metric => {
              const requirementNames = getAssignedRequirementNames(metric);
              const hasAssignedRequirements =
                Array.isArray(metric.requirements) &&
                metric.requirements.length > 0;

              const backendType =
                metric.backend_type?.type_value?.toLowerCase();
              const isClickableMetric =
                backendType === 'custom' || backendType === 'rhesis';

              return (
                <MetricCard
                  key={metric.id}
                  type={
                    isValidMetricType(metric.metric_type?.type_value)
                      ? metric.metric_type.type_value
                      : undefined
                  }
                  title={metric.name}
                  description={metric.description}
                  backend={metric.backend_type?.type_value}
                  metricType={metric.metric_type?.type_value}
                  scoreType={metric.score_type}
                  metricScope={metric.metric_scope}
                  usedIn={requirementNames}
                  showUsage={true}
                  onClick={
                    assignMode
                      ? () => {
                          setSelectedMetric(metric);
                          setAssignDialogOpen(true);
                        }
                      : isClickableMetric
                        ? () => router.push(`/metrics/${metric.id}`)
                        : undefined
                  }
                  onDelete={
                    canDelete &&
                    !hasAssignedRequirements &&
                    metric.backend_type?.type_value?.toLowerCase() === 'custom'
                      ? () => handleDeleteMetric(metric.id, metric.name)
                      : undefined
                  }
                />
              );
            })}
          </Box>
          {totalCount > 0 && (
            <TablePagination
              component="div"
              count={totalCount}
              page={page}
              onPageChange={(_event, newPage) => onPageChange(newPage)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={event => {
                onRowsPerPageChange(parseInt(event.target.value, 10));
              }}
              rowsPerPageOptions={[25, 50, 100]}
              labelRowsPerPage="Metrics per page:"
              sx={{ mb: 2 }}
            />
          )}
          {/* Dialogs */}
          <DeleteModal
            open={deleteMetricDialogOpen}
            onClose={handleCancelDeleteMetric}
            onConfirm={handleConfirmDeleteMetric}
            isLoading={isDeletingMetric}
            itemType="metric"
            itemName={metricToDeleteCompletely?.name}
          />
          <SelectRequirementsDialog
            open={assignDialogOpen}
            onClose={() => {
              setAssignDialogOpen(false);
              setSelectedMetric(null);
            }}
            onSelect={handleAssignMetric}
            excludeRequirementIds={(selectedMetric?.requirements ?? []).map(
              r => r.id
            )}
          />
        </>
      )}
    </PageLayout>
  );
}
