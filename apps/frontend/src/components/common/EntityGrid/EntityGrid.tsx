'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Paper } from '@mui/material';
import type { GridColDef, GridRowModel, GridRowParams } from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import GridStateGate from '@/components/common/GridStateGate';
import { DeleteModal } from '@/components/common/DeleteModal';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import {
  EntityGridToolbarContext,
  EntityGridToolbarSlot,
  type EntityGridToolbarState,
} from './EntityGridToolbar';
import { useList } from '@/hooks/useList';
import {
  useBulkDelete,
  type BulkDeleteActionsState,
} from '@/hooks/useBulkDelete';
import { useCan } from '@/components/common/Can';
import { can } from '@/utils/affordances';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications as useNotificationBadges } from '@/contexts/NotificationsContext';
import { HIGHLIGHTED_ROW_CLASS } from '@/constants/notifications';
import type { WithPermittedActions } from '@/types/affordances';
import type { FilterSpecMap, FiltersOf } from '@/utils/list';
import type { EntityGridProps, EntityGridSelectionContext } from './types';

function capitalize(label: string): string {
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const NO_HIGHLIGHTS: string[] = [];

/**
 * The standard list grid: descriptor-driven fetch, toolbar (search + pills +
 * filter drawer), dismissible error, selection/bulk-delete, trailing actions
 * column, confirm modal, empty state, and card chrome — composed once so a
 * grid file is columns + a descriptor + its genuinely unique parts.
 */
export default function EntityGrid<
  T,
  S extends FilterSpecMap,
  TDrawer = Record<string, never>,
  TBulk extends BulkDeleteActionsState = BulkDeleteActionsState,
>({
  descriptor,
  columns,
  toFilters,
  emptyState,
  initialData,
  initialTotalCount,
  refreshTrigger,
  extraFilters,
  enabled,
  pollMs,
  onDataChange,
  mapRows,
  getRowId,
  extraLoading = false,
  searchPlaceholder,
  pills,
  drawer,
  externalFilters,
  toolbarRight,
  showGridButtons = true,
  showExport = true,
  selectionLabel,
  getRowUrl,
  onRowClick,
  highlightSection,
  editAction,
  extraRowActions,
  rowActionsWidth,
  onBulkActionsChange,
  buildBulkActions,
  renderSelectionExtras,
  embedded = false,
  banner,
  persistState = true,
  storageKey,
  serverSort = true,
  pageSizeOptions,
  density,
  initialState,
  sx,
}: EntityGridProps<T, S, TDrawer, TBulk>) {
  const router = useRouter();
  const deleteSpec = descriptor.delete;

  // ── Toolbar-owned state ────────────────────────────────────────────────────
  const allPillValue = pills?.allValue ?? 'all';
  const [searchQuery, setSearchQuery] = useState('');
  const [pillValue, setPillValue] = useState(allPillValue);
  const emptyDrawer = drawer?.empty ?? ({} as TDrawer);
  const [drawerFilters, setDrawerFilters] = useState<TDrawer>(emptyDrawer);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);

  const filters = useMemo(
    () => ({
      ...toFilters({
        search: searchQuery,
        pill: pillValue === allPillValue ? '' : pillValue,
        drawer: drawerFilters,
      }),
      ...externalFilters,
    }),
    [
      toFilters,
      searchQuery,
      pillValue,
      allPillValue,
      drawerFilters,
      externalFilters,
    ]
  ) as FiltersOf<S>;

  // ── Data ───────────────────────────────────────────────────────────────────
  const {
    data,
    totalCount,
    isLoading,
    error: rawError,
    refresh,
    paginationModel,
    onPaginationModelChange,
    sortModel,
    onSortModelChange,
  } = useList(descriptor, {
    filters,
    extraFilters,
    enabled,
    initialData,
    initialTotalCount,
    pollMs,
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);
  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  // Gate on "has the first load settled", not on isLoading: a refetch (search
  // keystroke, pill change) must keep the grid mounted or the toolbar's search
  // input unmounts mid-typing and loses focus. Refetches show the DataGrid's
  // own loading overlay instead.
  const hasLoadedOnce = useRef(initialData !== undefined);
  if (!isLoading) hasLoadedOnce.current = true;

  // Compare against the last seen value rather than a "first run" flag: Strict
  // Mode's double-invoked mount effect would consume the flag and then call
  // refresh(), causing a redundant fetch (and a grid flash on empty pages).
  const lastRefreshTrigger = useRef(refreshTrigger);
  useEffect(() => {
    if (lastRefreshTrigger.current === refreshTrigger) return;
    lastRefreshTrigger.current = refreshTrigger;
    refresh();
    // Only refreshTrigger (bumped by the page after a create) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  const hasActiveDrawerFilters = drawer
    ? drawer.countActive(drawerFilters) > 0
    : false;
  const activeFilterCount = drawer ? drawer.countActive(drawerFilters) : 0;
  const filtersActive =
    !!searchQuery || pillValue !== allPillValue || hasActiveDrawerFilters;

  const onDataChangeRef = useRef(onDataChange);
  onDataChangeRef.current = onDataChange;
  useEffect(() => {
    onDataChangeRef.current?.(data, totalCount, filtersActive);
  }, [data, totalCount, filtersActive]);

  // ── Delete / selection ─────────────────────────────────────────────────────
  // Called unconditionally (rules of hooks); inert when there is no delete spec.
  const ambientCanDelete = useCan(deleteSpec?.capability ?? '');
  const canDeleteRow = useCallback(
    (row: Record<string, unknown>): boolean => {
      if (!deleteSpec) return false;
      if (deleteSpec.capabilityMode === 'row') {
        return can(
          row as unknown as WithPermittedActions,
          deleteSpec.capability
        );
      }
      return ambientCanDelete;
    },
    [deleteSpec, ambientCanDelete]
  );

  const bulkDeleteFn = useMemo(
    () =>
      deleteSpec?.bulk
        ? (ids: string[]) => deleteSpec.bulk!(new ApiClientFactory(), ids)
        : undefined,
    [deleteSpec]
  );
  const deleteOneFn = useMemo(
    () =>
      deleteSpec?.one
        ? (id: string) => deleteSpec.one!(new ApiClientFactory(), id)
        : undefined,
    [deleteSpec]
  );

  const {
    checkboxSelectionMode,
    setCheckboxSelectionMode,
    selectedRows,
    setSelectedRows,
    handleSelectionChange,
    pendingDeleteId,
    deleteModalOpen,
    isDeleting,
    requestDelete,
    confirmDelete,
    cancelDelete,
  } = useBulkDelete({
    bulkDeleteFn,
    deleteOneFn,
    onSuccess: refresh,
    itemLabelSingular: deleteSpec?.labelSingular ?? 'item',
    itemLabelPlural: deleteSpec?.labelPlural ?? 'items',
    getSkippedCount: deleteSpec?.getSkippedCount?.bind(deleteSpec),
    skippedReason: deleteSpec?.skippedReason,
  });

  const rows: GridRowModel[] = useMemo(
    () => (mapRows ? mapRows(data) : (data as GridRowModel[])),
    [mapRows, data]
  );

  // ── Bulk-actions bridge ────────────────────────────────────────────────────
  // Pushed from here (not useBulkDelete's own bridge) so extended states like
  // Tests' assignDisabled re-evaluate when the selection itself changes, and
  // refs keep the effect from re-firing on every new closure identity.
  const clearSelection = useCallback(
    () => setSelectedRows([]),
    [setSelectedRows]
  );
  const selectionCtx: EntityGridSelectionContext<T> = useMemo(() => {
    const selectedIds = selectedRows.map(String);
    const idOf = (row: GridRowModel) =>
      getRowId ? getRowId(row) : String((row as { id?: unknown }).id);
    return {
      selectedIds,
      selectedRows: rows
        .filter(row => selectedIds.includes(idOf(row)))
        .map(row => row as T),
      clearSelection,
      refresh,
    };
  }, [selectedRows, rows, getRowId, clearSelection, refresh]);

  const buildBulkActionsRef = useRef(buildBulkActions);
  buildBulkActionsRef.current = buildBulkActions;
  const onBulkActionsChangeRef = useRef(onBulkActionsChange);
  onBulkActionsChangeRef.current = onBulkActionsChange;
  const requestDeleteRef = useRef(requestDelete);
  requestDeleteRef.current = requestDelete;
  const selectionCtxRef = useRef(selectionCtx);
  selectionCtxRef.current = selectionCtx;

  const showBulkActions = checkboxSelectionMode && selectedRows.length > 0;
  useEffect(() => {
    const push = onBulkActionsChangeRef.current;
    if (!push) return;
    const base: BulkDeleteActionsState = {
      visible: showBulkActions,
      onDelete: () => requestDeleteRef.current(),
    };
    const build = buildBulkActionsRef.current;
    push(build ? build(base, selectionCtxRef.current) : (base as TBulk));
    // selectedRows (not just visibility) so extended bulk state re-evaluates.
  }, [showBulkActions, selectedRows]);

  useEffect(() => {
    return () => {
      const push = onBulkActionsChangeRef.current;
      if (!push) return;
      const base: BulkDeleteActionsState = {
        visible: false,
        onDelete: () => {},
      };
      const build = buildBulkActionsRef.current;
      push(build ? build(base, selectionCtxRef.current) : (base as TBulk));
    };
  }, []);

  // ── Row navigation / highlight ─────────────────────────────────────────────
  const { highlightedIds, clearHighlight } = useNotificationBadges();
  const highlights = highlightSection
    ? highlightedIds(highlightSection)
    : NO_HIGHLIGHTS;

  const getRowClassName = useCallback(
    (params: GridRowParams) =>
      highlights.includes(String(params.id)) ? HIGHLIGHTED_ROW_CLASS : '',
    [highlights]
  );

  const resolveRowUrl = useCallback(
    (row: GridRowModel) => getRowUrl?.(row as T),
    [getRowUrl]
  );

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      if (highlightSection) {
        clearHighlight(highlightSection, String(params.id));
      }
      if (onRowClick) {
        onRowClick(params);
        return;
      }
      const url = resolveRowUrl(params.row);
      if (url) router.push(url);
    },
    [highlightSection, clearHighlight, onRowClick, resolveRowUrl, router]
  );

  const wantsRowClick = !!onRowClick || !!getRowUrl;

  // ── Actions column ─────────────────────────────────────────────────────────
  const deleteEnabled = !!deleteSpec && !!(deleteSpec.bulk || deleteSpec.one);

  const editActionRef = useRef(editAction);
  editActionRef.current = editAction;
  const gridColumns: GridColDef[] = useMemo(() => {
    const edit = editAction === false ? undefined : editAction;
    const showEditAction =
      editAction !== false && !!(edit?.onClick || getRowUrl);
    const hasAnyAction =
      showEditAction || (extraRowActions?.length ?? 0) > 0 || deleteEnabled;
    if (!hasAnyAction) return columns;

    const actionsCol = createRowActionsColumn({
      ...(showEditAction && {
        onEdit: (id: string, row: Record<string, unknown>) => {
          if (edit?.onClick) {
            edit.onClick(id, row as T);
            return;
          }
          const url = getRowUrl?.(row as T);
          if (url) router.push(url);
        },
        canEdit: (row: Record<string, unknown>) =>
          edit?.can ? edit.can(row as T) : true,
      }),
      extraActions: extraRowActions,
      ...(deleteEnabled && {
        onDelete: (id: string) => requestDelete(id),
        canDelete: canDeleteRow,
      }),
      width: rowActionsWidth,
    });
    return [...columns, actionsCol];
  }, [
    columns,
    editAction,
    getRowUrl,
    extraRowActions,
    deleteEnabled,
    requestDelete,
    canDeleteRow,
    rowActionsWidth,
    router,
  ]);

  // ── Toolbar context ────────────────────────────────────────────────────────
  const openFilterDrawer = useMemo(
    () => (drawer ? () => setFilterDrawerOpen(true) : undefined),
    [drawer]
  );

  const handleDrawerApply = useCallback(
    (applied: TDrawer) => {
      const newPill = drawer?.pillFromApply?.(applied, drawerFilters);
      setDrawerFilters(applied);
      if (newPill !== undefined) {
        setPillValue(newPill === '' ? allPillValue : newPill);
      }
    },
    [drawer, drawerFilters, allPillValue]
  );

  const toolbarContextValue: EntityGridToolbarState = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      searchPlaceholder: searchPlaceholder ?? `Search ${descriptor.resource}…`,
      pills: pills ? { tabs: pills.tabs } : undefined,
      pillValue,
      setPillValue,
      openFilterDrawer,
      hasActiveDrawerFilters,
      activeFilterCount,
      selection: deleteSpec?.bulk
        ? {
            checked: checkboxSelectionMode,
            onChange: setCheckboxSelectionMode,
            label: selectionLabel ?? `Select ${descriptor.resource}`,
          }
        : undefined,
      toolbarRight,
      showGridButtons,
      showExport,
    }),
    [
      searchQuery,
      searchPlaceholder,
      descriptor.resource,
      pills,
      pillValue,
      openFilterDrawer,
      hasActiveDrawerFilters,
      activeFilterCount,
      deleteSpec?.bulk,
      checkboxSelectionMode,
      setCheckboxSelectionMode,
      selectionLabel,
      toolbarRight,
      showGridButtons,
      showExport,
    ]
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  const deleteCount = pendingDeleteId ? 1 : selectedRows.length;
  const loading = isLoading || extraLoading;

  const content = (
    <EntityGridToolbarContext.Provider value={toolbarContextValue}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
          {error}
        </Alert>
      )}
      {banner}
      <Box sx={{ position: 'relative' }}>
        <BaseDataGrid
          rows={rows}
          columns={gridColumns}
          loading={loading}
          getRowId={getRowId}
          serverSidePagination={true}
          totalRows={totalCount}
          paginationModel={paginationModel}
          onPaginationModelChange={onPaginationModelChange}
          pageSizeOptions={pageSizeOptions}
          toolbarSlot={EntityGridToolbarSlot}
          disablePaperWrapper={true}
          persistState={persistState}
          storageKey={storageKey}
          density={density}
          initialState={initialState}
          sx={sx}
          {...(serverSort && {
            sortingMode: 'server' as const,
            sortModel,
            onSortModelChange,
          })}
          getRowUrl={
            checkboxSelectionMode || !getRowUrl ? undefined : resolveRowUrl
          }
          onRowClick={
            checkboxSelectionMode || !wantsRowClick ? undefined : handleRowClick
          }
          getRowClassName={highlightSection ? getRowClassName : undefined}
          checkboxSelection={checkboxSelectionMode}
          disableRowSelectionOnClick={checkboxSelectionMode || undefined}
          rowSelectionModel={checkboxSelectionMode ? selectedRows : []}
          onRowSelectionModelChange={
            checkboxSelectionMode ? handleSelectionChange : undefined
          }
          isRowSelectable={
            checkboxSelectionMode && deleteSpec?.capabilityMode === 'row'
              ? params => canDeleteRow(params.row)
              : undefined
          }
        />

        {deleteEnabled && (
          <DeleteModal
            open={deleteModalOpen}
            onClose={cancelDelete}
            onConfirm={confirmDelete}
            isLoading={isDeleting}
            title={
              deleteCount === 1
                ? `Delete ${capitalize(deleteSpec?.labelSingular ?? 'item')}`
                : `Delete ${capitalize(deleteSpec?.labelPlural ?? 'items')}`
            }
            message={
              deleteSpec?.confirmMessage
                ? deleteSpec.confirmMessage(deleteCount)
                : deleteCount === 1
                  ? `Are you sure you want to delete this ${deleteSpec?.labelSingular}? This action cannot be undone.`
                  : `Are you sure you want to delete ${deleteCount} ${deleteSpec?.labelPlural}? This action cannot be undone.`
            }
            itemType={deleteSpec?.labelPlural}
          />
        )}
      </Box>

      {drawer?.render({
        open: filterDrawerOpen,
        onClose: () => setFilterDrawerOpen(false),
        filters: drawerFilters,
        onApply: handleDrawerApply,
      })}

      {renderSelectionExtras?.(selectionCtx)}
    </EntityGridToolbarContext.Provider>
  );

  return (
    <GridStateGate
      active={!embedded}
      data={hasLoadedOnce.current ? {} : null}
      error={error}
      isEmpty={!loading && totalCount === 0 && !filtersActive}
      emptyState={emptyState}
    >
      {embedded ? content : <Paper sx={GRID_PAPER_SX}>{content}</Paper>}
    </GridStateGate>
  );
}
