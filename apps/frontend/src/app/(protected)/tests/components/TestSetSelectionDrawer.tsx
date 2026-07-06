'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type { GridColDef } from '@mui/x-data-grid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import { TYPE_NAMES } from '@/constants/test-types';
import { useTypeLookups } from '@/hooks/useLookups';

const columns: GridColDef[] = [
  { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
  {
    field: 'description',
    headerName: 'Description',
    flex: 2,
    minWidth: 200,
  },
];

interface TestSetSelectionDrawerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (testSets: TestSet[]) => Promise<void>;
  sessionToken: string;
  testTypeValue?: string;
}

export default function TestSetSelectionDrawer({
  open,
  onClose,
  onSelect,
  sessionToken,
  testTypeValue,
}: TestSetSelectionDrawerProps) {
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(false);
  const notifications = useNotifications();

  const escapedTestTypeValue = testTypeValue?.replace(/'/g, "''");
  const { data: resolvedTypes } = useTypeLookups(
    sessionToken,
    escapedTestTypeValue
      ? `type_name eq '${TYPE_NAMES.TEST_SET_TYPE}' and type_value eq '${escapedTestTypeValue}'`
      : '',
    !!escapedTestTypeValue && open
  );
  const resolvedTestSetTypeId = resolvedTypes?.[0]?.id as string | undefined;

  const fetchTestSets = useCallback(async () => {
    if (!open) return;

    setLoading(true);
    try {
      const testSetsClient = new ApiClientFactory(sessionToken).getTestSetsClient();
      const typeFilter = resolvedTestSetTypeId
        ? `test_set_type_id eq '${resolvedTestSetTypeId}'`
        : undefined;

      const sets = await testSetsClient.getTestSets({
        sort_by: 'name',
        sort_order: 'asc',
        limit: 100,
        ...(typeFilter && { $filter: typeFilter }),
      });
      setTestSets(sets.data);
    } catch {
      notifications.show('Failed to load test sets', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setLoading(false);
    }
  }, [sessionToken, open, notifications, resolvedTestSetTypeId]);

  useEffect(() => {
    if (open) {
      void fetchTestSets();
    }
  }, [open, fetchTestSets]);

  const handleAssign = async (selectedIds: string[]) => {
    const selected = testSets.filter(ts =>
      selectedIds.includes(String(ts.id))
    );
    if (selected.length === 0) return;

    await onSelect(selected);
  };

  return (
    <AssignEntityDrawer
      open={open}
      onClose={onClose}
      title="Assign to Test Set"
      rows={testSets}
      columns={columns}
      loading={loading}
      getRowId={row => String(row.id)}
      onAssign={handleAssign}
      saveButtonText="Assign"
      searchPlaceholder="Search test sets…"
    />
  );
}
