'use client';

import React, { useCallback, useMemo, useRef, useState } from 'react';
import type { GridColDef } from '@mui/x-data-grid';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import { DeleteModal } from '@/components/common/DeleteModal';
import { getTestSetTestColumns } from './testSetTestColumns';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  countActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';
import { testSetTestsList } from './list';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { LinkOffIcon } from '@/components/icons';
import type { RowExtraAction } from '@/components/common/createRowActionsColumn';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

interface TestSetTestsGridProps {
  testSetId: string;
  testSetType?: string;
  /** Server-prefetched first page (default sort, no filters); skips the mount fetch. */
  initialTests?: TestDetail[];
  initialTotalCount?: number;
  onTotalCountChange?: (count: number) => void;
  /** Bumped by the page (e.g. after an assign) to trigger a re-fetch. */
  refreshTrigger?: number;
}

function toFilters(state: EntityGridFilterState<TestFilters>) {
  return {
    search: state.search,
    testType: state.drawer.testType,
    requirement: state.drawer.requirement,
    category: state.drawer.category,
    topic: state.drawer.topic,
    tagsPresence: state.drawer.tags,
    commentsPresence: state.drawer.comments,
    tasksPresence: state.drawer.tasks,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TestFilters> = {
  empty: EMPTY_TEST_FILTERS,
  countActive: countActiveTestFilters,
  render: props => (
    <TestFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

export default function TestSetTestsGrid({
  testSetId,
  testSetType,
  initialTests,
  initialTotalCount,
  onTotalCountChange,
  refreshTrigger,
}: TestSetTestsGridProps) {
  const notifications = useNotifications();
  const canEditTestSet = useCan(Capability.TestSet.UPDATE);
  const canExport = useCan(Capability.TestSet.EXPORT);

  const descriptor = useMemo(() => testSetTestsList(testSetId), [testSetId]);
  const columns: GridColDef[] = useMemo(
    () => getTestSetTestColumns(testSetType),
    [testSetType]
  );

  const onTotalCountChangeRef = useRef(onTotalCountChange);
  onTotalCountChangeRef.current = onTotalCountChange;
  const handleDataChange = useCallback(
    (_data: TestDetail[], totalCount: number, filtersActive: boolean) => {
      if (!filtersActive) {
        onTotalCountChangeRef.current?.(totalCount);
      }
    },
    []
  );

  const [removeTarget, setRemoveTarget] = useState<TestDetail | null>(null);
  const [removing, setRemoving] = useState(false);

  const handleRemoveClick = useCallback((row: TestDetail) => {
    setRemoveTarget(row);
  }, []);

  const handleCancelRemove = useCallback(() => setRemoveTarget(null), []);

  const makeConfirmRemove = useCallback(
    (refresh: () => void) => async () => {
      if (!removeTarget) return;
      try {
        setRemoving(true);
        const factory = new ApiClientFactory();
        await factory
          .getTestSetsClient()
          .disassociateTestsFromTestSet(testSetId, [String(removeTarget.id)]);
        notifications.show('Test removed from test set', {
          severity: 'success',
          autoHideDuration: 4000,
        });
        setRemoveTarget(null);
        refresh();
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : 'Failed to remove test from test set. Please try again.';
        notifications.show(message, { severity: 'error' });
      } finally {
        setRemoving(false);
      }
    },
    [removeTarget, testSetId, notifications]
  );

  const extraRowActions: RowExtraAction[] = useMemo(
    () => [
      {
        key: 'remove',
        icon: LinkOffIcon,
        tooltip: 'Remove from test set',
        onClick: (_id: string, row: Record<string, unknown>) =>
          handleRemoveClick(row as unknown as TestDetail),
        can: () => canEditTestSet,
        hoverColor: 'error.main' as const,
      },
    ],
    [handleRemoveClick, canEditTestSet]
  );

  return (
    <EntityGrid<TestDetail, typeof descriptor.filters, TestFilters>
      descriptor={descriptor}
      columns={columns}
      toFilters={toFilters}
      emptyState={null}
      embedded
      initialData={initialTests}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      onDataChange={handleDataChange}
      searchPlaceholder="Search tests…"
      drawer={drawerAdapter}
      showExport={canExport}
      getRowUrl={row => `/tests/${row.id}`}
      editAction={false}
      extraRowActions={extraRowActions}
      pageSizeOptions={[10, 25, 50]}
      renderSelectionExtras={ctx => (
        <DeleteModal
          open={removeTarget !== null}
          onClose={handleCancelRemove}
          onConfirm={makeConfirmRemove(ctx.refresh)}
          isLoading={removing}
          title="Remove from Test Set"
          message="Remove this test from the test set? The test itself will not be deleted."
          confirmButtonText={removing ? 'Removing…' : 'Remove'}
        />
      )}
    />
  );
}
