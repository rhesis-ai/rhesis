'use client';

import * as React from 'react';
import { useCallback, useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowParams,
} from '@mui/x-data-grid';
import Button from '@mui/material/Button';
import DownloadIcon from '@mui/icons-material/Download';
import HistoryIcon from '@mui/icons-material/History';
import { Can } from '@/components/common/Can';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { Capability } from '@/constants/capabilities';
import { buildListFilter } from '@/utils/list';
import {
  RESOURCE_AREAS,
  resourceDisplayName,
} from '../../shared/resource-catalog';
import { AUDIT_EVENTS_SORT_FIELD } from '../api/audit-log-client';
import {
  EMPTY_AUDIT_EVENT_FILTERS,
  countActiveAuditEventFilters,
  type AuditEventFilters,
} from '../filters';
import {
  actionLabel,
  actorDisplay,
  channelLabel,
  splitAction,
} from '../labels';
import { auditEventsList, type AuditEventListFilters } from '../list';
import {
  AuditOutcome,
  FieldChangeKind,
  type AuditEvent,
  type AuditEventRow,
} from '../types';
import AuditEventDrawer from './AuditEventDrawer';
import AuditExportDialog from './AuditExportDialog';
import AuditEventFilterDrawer from './AuditEventFilterDrawer';
import { formatValue, monoSx } from './AuditChanges';

const ALL_PILL = 'all';
const CATEGORY_PILLS = [
  { label: 'All', value: ALL_PILL },
  ...RESOURCE_AREAS.map(area => ({ label: area.label, value: area.id })),
];
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const STORAGE_KEY = 'audit-log-events';
const ORG_LEVEL_LABEL = 'Organization';

function toFilters(
  state: EntityGridFilterState<AuditEventFilters>
): AuditEventListFilters {
  return {
    search: state.search,
    area: state.pill,
    ...state.drawer,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<AuditEventFilters> = {
  empty: EMPTY_AUDIT_EVENT_FILTERS,
  countActive: countActiveAuditEventFilters,
  render: props => (
    <AuditEventFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

/** One line for the Details column: what changed, in brief. */
export function changeSummary(event: AuditEvent): string {
  const { changes } = event;
  if (Array.isArray(changes)) {
    if (changes.length === 0) return '';
    if (changes.length > 1) return `${changes.length} fields changed`;
    const [only] = changes;
    if (only.kind !== FieldChangeKind.VALUE) return `${only.field} changed`;
    return `${only.field}: ${formatValue(only.before)} → ${formatValue(only.after)}`;
  }
  if (changes && typeof changes.count === 'number') {
    return `${changes.count.toLocaleString()} items`;
  }
  return '';
}

function TwoLines({
  primary,
  secondary,
  error = false,
}: {
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  error?: boolean;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        height: '100%',
        minWidth: 0,
      }}
    >
      <Typography
        variant="body2"
        noWrap
        color={error ? 'error.main' : 'text.primary'}
      >
        {primary}
      </Typography>
      {secondary && (
        <Typography variant="caption" color="text.secondary" noWrap>
          {secondary}
        </Typography>
      )}
    </Box>
  );
}

export default function AuditEventsGrid() {
  const [openEventId, setOpenEventId] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  // The $filter of what the list shows, so an export matches it exactly.
  const [exportFilter, setExportFilter] = useState<string | undefined>();
  const onFiltersChange = useCallback(
    (filters: AuditEventListFilters) =>
      setExportFilter(buildListFilter(auditEventsList, filters)),
    []
  );

  const onRowClick = useCallback(
    (params: GridRowParams) => setOpenEventId(String(params.id)),
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: AUDIT_EVENTS_SORT_FIELD,
        headerName: 'Time',
        flex: 1,
        minWidth: 170,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Typography variant="body2">
            {new Date(params.row.occurred_at).toLocaleString()}
          </Typography>
        ),
      },
      {
        field: 'actor_label',
        headerName: 'Actor',
        flex: 1.4,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => {
          const actor = actorDisplay(params.row);
          return <TwoLines primary={actor.name} secondary={actor.detail} />;
        },
      },
      {
        field: 'action',
        headerName: 'Action',
        flex: 1.4,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <TwoLines
            primary={actionLabel(params.row.action, params.row.outcome)}
            secondary={
              <Box component="span" sx={monoSx}>
                {params.row.action}
              </Box>
            }
            error={params.row.outcome !== AuditOutcome.SUCCESS}
          />
        ),
      },
      {
        field: 'resource_label',
        headerName: 'Resource',
        flex: 1.4,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <TwoLines
            primary={params.row.resource_label ?? '—'}
            secondary={resourceDisplayName(
              splitAction(params.row.action).resource
            )}
          />
        ),
      },
      {
        field: 'project_id',
        headerName: 'Project',
        flex: 1,
        minWidth: 130,
        sortable: false,
        // Org-level events have no project.
        renderCell: (params: GridRenderCellParams<AuditEventRow>) => {
          const { project_id: id, project_name: name } = params.row;
          return (
            <Typography variant="body2" noWrap>
              {id ? (name ?? id) : ORG_LEVEL_LABEL}
            </Typography>
          );
        },
      },
      {
        field: 'channel',
        headerName: 'Source',
        flex: 0.7,
        minWidth: 100,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Typography variant="body2">
            {channelLabel(params.row.channel)}
          </Typography>
        ),
      },
      {
        field: 'changes',
        headerName: 'Details',
        flex: 1.6,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Typography variant="body2" color="text.secondary" noWrap>
            {changeSummary(params.row)}
          </Typography>
        ),
      },
    ],
    []
  );

  return (
    <>
      <EntityGrid<
        AuditEventRow,
        typeof auditEventsList.filters,
        AuditEventFilters
      >
        descriptor={auditEventsList}
        columns={columns}
        toFilters={toFilters}
        emptyState={
          <EntityEmptyState
            icon={HistoryIcon}
            title="No events yet"
            description="Changes to access, tests, metrics and configuration show up here as people and jobs make them."
          />
        }
        searchPlaceholder="Search actor, resource or action id (endpoint.updated)…"
        pills={{ tabs: CATEGORY_PILLS, allValue: ALL_PILL }}
        drawer={drawerAdapter}
        onFiltersChange={onFiltersChange}
        toolbarRight={
          <Can capability={Capability.AuditLog.EXPORT}>
            <Button
              size="small"
              startIcon={<DownloadIcon />}
              onClick={() => setExportOpen(true)}
            >
              Export
            </Button>
          </Can>
        }
        onRowClick={onRowClick}
        editAction={false}
        showGridButtons={false}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        storageKey={STORAGE_KEY}
      />
      <AuditEventDrawer
        eventId={openEventId}
        onClose={() => setOpenEventId(null)}
        onSelect={setOpenEventId}
      />
      <AuditExportDialog
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        filter={exportFilter}
      />
    </>
  );
}
