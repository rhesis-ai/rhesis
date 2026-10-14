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
import Tooltip from '@mui/material/Tooltip';
import { alpha, type Theme } from '@mui/material/styles';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import DownloadIcon from '@mui/icons-material/Download';
import HistoryIcon from '@mui/icons-material/History';
import { Can } from '@/components/common/Can';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { Capability } from '@/constants/capabilities';
import { ICON_COLUMN_WIDTH } from '@/styles/theme-constants';
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
import { actorDisplay, channelLabel, splitAction } from '../labels';
import { auditEventsList, type AuditEventListFilters } from '../list';
import { useMemberRoles } from '../hooks/useMemberRoles';
import {
  AuditActorType,
  AuditOutcome,
  FieldChangeKind,
  type AuditEvent,
  type AuditEventRow,
} from '../types';
import AuditEventDrawer from './AuditEventDrawer';
import AuditExportDialog from './AuditExportDialog';
import AuditEventFilterDrawer from './AuditEventFilterDrawer';
import { formatValue, monoSx } from './AuditChanges';
import { ActionChip, ActorAvatar, OutlinedTag } from './tones';

const ALL_PILL = 'all';
const CATEGORY_PILLS = [
  { label: 'All', value: ALL_PILL },
  ...RESOURCE_AREAS.map(area => ({ label: area.label, value: area.id })),
];
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const STORAGE_KEY = 'audit-log-events';
const ORG_LEVEL_LABEL = 'Organization';
const FAILED_ROW_CLASS = 'audit-row-failed';

const TIME_FORMAT: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  // 24-hour, as in the design; AM/PM does not fit the column.
  hourCycle: 'h23',
};

/** "CEST", so the column says which clock its times are on. */
function timeZoneName(): string | undefined {
  return new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' })
    .formatToParts(new Date())
    .find(part => part.type === 'timeZoneName')?.value;
}

const failedRow = (row: AuditEventRow) =>
  row.outcome === AuditOutcome.SUCCESS ? undefined : FAILED_ROW_CLASS;

const gridSx = {
  [`& .${FAILED_ROW_CLASS}`]: {
    bgcolor: (t: Theme) =>
      alpha(t.palette.error.main, t.palette.action.hoverOpacity),
  },
};

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
  secondaryFirst = false,
}: {
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  /** The secondary line as a small label above, as for a resource's type. */
  secondaryFirst?: boolean;
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
      {secondaryFirst && secondary && (
        <Typography variant="caption" color="text.secondary" noWrap>
          {secondary}
        </Typography>
      )}
      <Typography variant="body2" noWrap>
        {primary}
      </Typography>
      {!secondaryFirst && secondary && (
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

  const zone = useMemo(timeZoneName, []);
  const memberRoles = useMemberRoles();

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: AUDIT_EVENTS_SORT_FIELD,
        headerName: zone ? `Time (${zone})` : 'Time',
        flex: 1,
        minWidth: 150,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Typography variant="body2" noWrap sx={monoSx}>
            {new Date(params.row.occurred_at).toLocaleString(
              undefined,
              TIME_FORMAT
            )}
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
          // Members show their role, as in the role editor; the email moves to a tooltip.
          const role =
            params.row.actor_type === AuditActorType.USER && params.row.actor_id
              ? memberRoles.get(params.row.actor_id)
              : undefined;
          const cell = (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                height: '100%',
                minWidth: 0,
              }}
            >
              <ActorAvatar
                name={actor.name}
                actorType={params.row.actor_type}
              />
              <TwoLines primary={actor.name} secondary={role ?? actor.detail} />
            </Box>
          );
          return role && actor.detail ? (
            <Tooltip title={actor.detail}>{cell}</Tooltip>
          ) : (
            cell
          );
        },
      },
      {
        field: 'action',
        headerName: 'Action',
        flex: 1.4,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <ActionChip
              action={params.row.action}
              outcome={params.row.outcome}
            />
          </Box>
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
            secondaryFirst
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
          <OutlinedTag>{channelLabel(params.row.channel)}</OutlinedTag>
        ),
      },
      {
        field: 'changes',
        headerName: 'Details',
        flex: 1.6,
        minWidth: 180,
        sortable: false,
        renderCell: (params: GridRenderCellParams<AuditEvent>) => (
          <Typography
            variant="body2"
            noWrap
            color={
              params.row.outcome === AuditOutcome.SUCCESS
                ? 'text.secondary'
                : 'error.main'
            }
          >
            {changeSummary(params.row)}
          </Typography>
        ),
      },
      {
        field: 'open',
        headerName: '',
        width: ICON_COLUMN_WIDTH,
        sortable: false,
        disableColumnMenu: true,
        renderCell: () => (
          // The row click opens the event; this is the visible cue.
          <Box
            aria-hidden
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'primary.main',
            }}
          >
            <ChevronRightIcon fontSize="small" />
          </Box>
        ),
      },
    ],
    [zone, memberRoles]
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
              Export CSV / JSONL
            </Button>
          </Can>
        }
        onRowClick={onRowClick}
        rowClassName={failedRow}
        sx={gridSx}
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
