import type React from 'react';
import type {
  GridColDef,
  GridDensity,
  GridInitialState,
  GridRowModel,
  GridRowParams,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import type { FilterSpecMap, FiltersOf, ListDescriptor } from '@/utils/list';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import type { ToolbarPillTab } from '@/components/common/GridToolbar';
import type { RowExtraAction } from '@/components/common/createRowActionsColumn';
import type { NotificationSection } from '@/constants/notifications';

/** Toolbar-owned state handed to `toFilters`. `pill` is `''` when the "all" pill is active. */
export interface EntityGridFilterState<TDrawer> {
  search: string;
  pill: string;
  drawer: TDrawer;
}

/** Adapter connecting an entity's filter drawer to EntityGrid's toolbar state. */
export interface EntityGridDrawerAdapter<TDrawer> {
  empty: TDrawer;
  /** Active-filter count shown as the filter button's badge. */
  countActive: (filters: TDrawer) => number;
  render: (props: {
    open: boolean;
    onClose: () => void;
    filters: TDrawer;
    onApply: (filters: TDrawer) => void;
  }) => React.ReactNode;
  /**
   * Sync the pill from an applied drawer state (e.g. Tasks' status). Return the
   * new pill value (`''` selects the "all" pill), or undefined to leave it.
   */
  pillFromApply?: (applied: TDrawer, previous: TDrawer) => string | undefined;
}

/** Live selection handed to `buildBulkActions` / `renderSelectionExtras`. */
export interface EntityGridSelectionContext<T> {
  selectedIds: string[];
  /** Selected rows resolved from the current page's data. */
  selectedRows: T[];
  clearSelection: () => void;
  refresh: () => void;
}

export interface EntityGridProps<
  T,
  S extends FilterSpecMap,
  TDrawer = Record<string, never>,
  TBulk extends BulkDeleteActionsState = BulkDeleteActionsState,
> {
  descriptor: ListDescriptor<T, S>;
  /** Data columns only — the trailing actions column is assembled internally. */
  columns: GridColDef[];
  /** Map toolbar-owned state onto the descriptor's filter keys. */
  toFilters: (state: EntityGridFilterState<TDrawer>) => FiltersOf<S>;
  emptyState: React.ReactNode;

  // ── data (pass-through to useList) ──
  initialData?: T[];
  initialTotalCount?: number;
  /** Bumped by the page (e.g. after a create) to trigger a re-fetch. */
  refreshTrigger?: number;
  /** OData clauses the toolbar doesn't own — project scoping, insights ids. */
  extraFilters?: (string | undefined)[];
  /** Extra fetch gate AND'd with the auth gate. */
  enabled?: boolean;
  /** Live polling — see `usePaginatedList`. */
  pollMs?: (data: T[]) => number | false;
  /** Fires whenever the page data or total changes (Annotations' count callback). */
  onDataChange?: (
    data: T[],
    totalCount: number,
    filtersActive: boolean
  ) => void;
  /** Derive the grid rows from the fetched entities (TestSets' processed rows). */
  mapRows?: (data: T[]) => GridRowModel[];
  /** Row id override for synthesized ids (Annotations). */
  getRowId?: (row: GridRowModel) => string;
  /** OR'd into the grid's loading flag (Endpoints' side-fetched projects). */
  extraLoading?: boolean;

  // ── toolbar ──
  searchPlaceholder?: string;
  /** Pill tabs; `allValue` (default `'all'`) maps to "no pill filter". */
  pills?: { tabs: ToolbarPillTab[]; allValue?: string };
  drawer?: EntityGridDrawerAdapter<TDrawer>;
  /** Descriptor-filter values owned by the caller, merged after `toFilters`. */
  externalFilters?: Partial<FiltersOf<S>>;
  /** Rendered before the Columns/Density/Export buttons (TestRuns' run-kind toggle). */
  toolbarRight?: React.ReactNode;
  /** Columns/Density/Export buttons. Default true; Jobs passes false. */
  showGridButtons?: boolean;
  /** CSV export button, gated separately (Tests: `useCan(TestSet.EXPORT)`). Default true. */
  showExport?: boolean;
  /** Selection toggle label. Default `Select ${descriptor.resource}`. */
  selectionLabel?: string;

  // ── rows / navigation ──
  getRowUrl?: (row: T) => string | undefined;
  /** Overrides URL navigation on left-click (Tests' drawer, Annotations' new tab). */
  onRowClick?: (params: GridRowParams) => void;
  /** Wire notification-badge row highlighting and clear-on-click. */
  highlightSection?: NotificationSection;

  // ── actions column ──
  /**
   * Edit icon. Defaults to navigating to `getRowUrl`; pass `false` to drop the
   * icon, or an object for a custom handler and/or per-row gate (omitting
   * `onClick` keeps the default navigation).
   */
  editAction?:
    | { onClick?: (id: string, row: T) => void; can?: (row: T) => boolean }
    | false;
  extraRowActions?: RowExtraAction[];
  rowActionsWidth?: number;

  // ── selection / bulk (active only when descriptor.delete?.bulk is set) ──
  onBulkActionsChange?: (state: TBulk) => void;
  /** Extend the delete-only bulk state (TestSets' Run, Tests' Assign, Explorer's Save). */
  buildBulkActions?: (
    base: BulkDeleteActionsState,
    ctx: EntityGridSelectionContext<T>
  ) => TBulk;
  /** Drawers/dialogs needing the live selection (RunDrawer, TestSetSelectionDrawer). */
  renderSelectionExtras?: (
    ctx: EntityGridSelectionContext<T>
  ) => React.ReactNode;

  // ── presentation ──
  /** Skip the Paper wrapper and loading/empty gate (embedded tabs). */
  embedded?: boolean;
  /** Rendered between the error alert and the grid (Tests' insights banner). */
  banner?: React.ReactNode;
  persistState?: boolean;
  storageKey?: string;
  /** Server-side sorting. Default true. */
  serverSort?: boolean;
  pageSizeOptions?: number[];
  density?: GridDensity;
  initialState?: GridInitialState;
  sx?: SxProps<Theme>;
}
