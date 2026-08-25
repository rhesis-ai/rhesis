import { useCallback, useRef, useState } from 'react';
import { BulkDeleteActionsState } from './useBulkDelete';

/**
 * Page-side half of the bulk-actions bridge: consumes the grid's
 * `onBulkActionsChange` callback and exposes just what the page needs to
 * render the delete action in its own FabGroup -- whether it's visible, and
 * a stable callback to trigger it. Every page with a bulk-select grid uses
 * this instead of re-deriving the same ref + state pair Tests originally
 * wrote by hand.
 */
export function useBulkActionsBridge() {
  const [visible, setVisible] = useState(false);
  const onDeleteRef = useRef<() => void>(() => {});

  const handleBulkActionsChange = useCallback(
    (actions: BulkDeleteActionsState) => {
      setVisible(actions.visible);
      onDeleteRef.current = actions.onDelete;
    },
    []
  );

  return {
    bulkActionsVisible: visible,
    onBulkDelete: () => onDeleteRef.current(),
    handleBulkActionsChange,
  };
}
