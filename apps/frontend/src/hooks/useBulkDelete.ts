import { useCallback, useState } from 'react';
import { useQueryClient, QueryKey } from '@tanstack/react-query';
import { GridRowSelectionModel } from '@mui/x-data-grid';
import { useNotifications } from '@/components/common/NotificationContext';

interface UseBulkDeleteOptions<TResp> {
  /** Calls the entity's `DELETE .../bulk` client method. */
  bulkDeleteFn: (ids: string[]) => Promise<TResp>;
  /** Invalidated after a successful delete so the grid refetches. */
  queryKey: QueryKey;
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
}

/**
 * Owns the checkbox-selection + confirm-modal + bulk-delete-call lifecycle
 * shared by every grid's bulk-select feature, so each grid wires state
 * instead of re-implementing it. Extracted from TestsGrid/ExplorerGrid,
 * which had each grown this independently.
 */
export function useBulkDelete<TResp = void>({
  bulkDeleteFn,
  queryKey,
  itemLabelSingular,
  itemLabelPlural,
  getSkippedCount,
  skippedReason,
}: UseBulkDeleteOptions<TResp>) {
  const notifications = useNotifications();
  const queryClient = useQueryClient();

  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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
    const idsToDelete = pendingDeleteId
      ? [pendingDeleteId]
      : (selectedRows as string[]);
    if (idsToDelete.length === 0) return;

    try {
      setIsDeleting(true);
      const response = await bulkDeleteFn(idsToDelete);

      const skipped = getSkippedCount?.(response) ?? 0;
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
      queryClient.invalidateQueries({ queryKey });
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
    getSkippedCount,
    skippedReason,
    itemLabelSingular,
    itemLabelPlural,
    notifications,
    queryClient,
    queryKey,
  ]);

  return {
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
