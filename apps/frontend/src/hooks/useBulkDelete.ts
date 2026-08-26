import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient, QueryKey } from '@tanstack/react-query';
import { GridRowSelectionModel } from '@mui/x-data-grid';
import { useNotifications } from '@/components/common/NotificationContext';

/** Pushed up to a page-level FabGroup via `onBulkActionsChange` -- see Tests. */
export interface BulkDeleteActionsState {
  visible: boolean;
  onDelete: () => void;
}

interface UseBulkDeleteOptions<TResp> {
  /** Calls the entity's `DELETE .../bulk` client method. Omit for entities
   * with only a single-row delete endpoint (pass `deleteOneFn` instead). */
  bulkDeleteFn?: (ids: string[]) => Promise<TResp>;
  /** Single-row delete used when `requestDelete(id)` targeted one row and
   * no bulk endpoint exists. */
  deleteOneFn?: (id: string) => Promise<unknown>;
  /** Invalidated after a successful delete so the grid refetches. Omit for
   * grids that don't fetch through react-query (e.g. Tokens) and use
   * `onSuccess` instead. */
  queryKey?: QueryKey;
  /** Called after a successful delete, in addition to any queryKey
   * invalidation -- for grids that manage their own data fetch/refetch
   * outside react-query. */
  onSuccess?: () => void;
  itemLabelSingular: string;
  itemLabelPlural: string;
  /**
   * Optional: for entities with an owner-only delete rule (Test Run, Task),
   * pull the count of ids that existed but weren't deletable out of the
   * response, so the second notification below can report them distinctly
   * from a plain success.
   */
  getSkippedCount?: (response: TResp) => number;
  /** Reason shown alongside the skipped count, e.g. "not yours to delete". */
  skippedReason?: string;
  /**
   * Reports selection-mode state up to a parent page so it can render the
   * delete action in its own FabGroup, matching Tests' top-right bulk
   * actions -- pass this through from the grid's own prop of the same name.
   */
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
}

/**
 * Owns the checkbox-selection-mode toggle + confirm-modal + bulk-delete-call
 * lifecycle shared by every grid's bulk-select feature, so each grid wires
 * state instead of re-implementing it. Extracted from TestsGrid, which had
 * grown this independently; every grid follows the same UX Tests already
 * established: a "Select X" toggle reveals checkboxes, and the delete action
 * surfaces in the page's own FabGroup (top right), not inline in the grid.
 */
export function useBulkDelete<TResp = void>({
  bulkDeleteFn,
  deleteOneFn,
  queryKey,
  onSuccess,
  itemLabelSingular,
  itemLabelPlural,
  getSkippedCount,
  skippedReason,
  onBulkActionsChange,
}: UseBulkDeleteOptions<TResp>) {
  const notifications = useNotifications();
  const queryClient = useQueryClient();

  const [checkboxSelectionMode, setCheckboxSelectionModeState] =
    useState(false);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const setCheckboxSelectionMode = useCallback((enabled: boolean) => {
    setCheckboxSelectionModeState(enabled);
    if (!enabled) {
      setSelectedRows([]);
    }
  }, []);

  const handleSelectionChange = useCallback(
    (model: GridRowSelectionModel) => setSelectedRows(model),
    []
  );

  /** Open the confirm modal for one row (pass an id) or the current selection (omit it). */
  const requestDelete = useCallback(
    (id?: string) => {
      if (id) {
        setPendingDeleteId(id);
        setDeleteModalOpen(true);
      } else if (selectedRows.length > 0) {
        setDeleteModalOpen(true);
      }
    },
    [selectedRows]
  );

  const cancelDelete = useCallback(() => {
    setDeleteModalOpen(false);
    setPendingDeleteId(null);
  }, []);

  const confirmDelete = useCallback(async () => {
    const idsToDelete = (
      pendingDeleteId ? [pendingDeleteId] : selectedRows
    ).map(String);
    if (idsToDelete.length === 0) return;

    try {
      setIsDeleting(true);
      let skipped = 0;
      if (bulkDeleteFn) {
        const response = await bulkDeleteFn(idsToDelete);
        skipped = getSkippedCount?.(response) ?? 0;
      } else if (deleteOneFn && pendingDeleteId) {
        await deleteOneFn(pendingDeleteId);
      } else {
        return;
      }

      const deletedCount = idsToDelete.length - skipped;
      if (deletedCount > 0) {
        const deletedLabel =
          deletedCount === 1 ? itemLabelSingular : itemLabelPlural;
        notifications.show(
          `Successfully deleted ${deletedCount} ${deletedLabel}`,
          {
            severity: 'success',
            autoHideDuration: 4000,
          }
        );
      }
      if (skipped > 0 && skippedReason) {
        const skippedLabel =
          skipped === 1 ? itemLabelSingular : itemLabelPlural;
        notifications.show(
          `${skipped} ${skippedLabel} skipped (${skippedReason})`,
          {
            severity: 'warning',
            autoHideDuration: 6000,
          }
        );
      }

      setSelectedRows([]);
      if (queryKey) {
        queryClient.invalidateQueries({ queryKey });
      }
      onSuccess?.();
    } catch {
      notifications.show(`Failed to delete ${itemLabelPlural}`, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
      // Clear here, not on success only: a stale id would retarget the next bulk delete.
      setPendingDeleteId(null);
    }
  }, [
    pendingDeleteId,
    selectedRows,
    bulkDeleteFn,
    deleteOneFn,
    getSkippedCount,
    skippedReason,
    itemLabelSingular,
    itemLabelPlural,
    notifications,
    queryClient,
    queryKey,
    onSuccess,
  ]);

  // Bridge selection state to a parent page's FabGroup, same mechanism as
  // Tests: a ref holds the latest handler so the effect only re-fires on the
  // values the parent actually needs to redraw for (visibility), not on
  // every render that creates a new requestDelete closure.
  const showBulkActions = checkboxSelectionMode && selectedRows.length > 0;
  const requestDeleteRef = useRef(requestDelete);
  requestDeleteRef.current = requestDelete;

  useEffect(() => {
    onBulkActionsChange?.({
      visible: showBulkActions,
      onDelete: () => requestDeleteRef.current(),
    });
  }, [showBulkActions, onBulkActionsChange]);

  useEffect(() => {
    return () => {
      onBulkActionsChange?.({ visible: false, onDelete: () => {} });
    };
  }, [onBulkActionsChange]);

  return {
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
  };
}
