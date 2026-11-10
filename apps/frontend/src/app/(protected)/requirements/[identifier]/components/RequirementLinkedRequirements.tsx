'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Typography } from '@mui/material';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import GridBadge from '@/components/common/GridBadge';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { LinkOffIcon } from '@/components/icons';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import type {
  RequirementOption,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import type { UUID } from 'crypto';
import RequirementDrawer, {
  type RequirementDetailsInput,
} from '../../components/RequirementDrawer';
import { useRequirementActions } from './useRequirementActions';

type Relation = 'Parent' | 'Child';

interface LinkedRequirementRow {
  id: string;
  name: string;
  description: string;
  relation: Relation;
}

type PickerRow = RequirementOption & { description?: string | null };

interface RequirementLinkedRequirementsProps {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
}

/** This requirement's parent and children, built like Linked Metrics. */
export default function RequirementLinkedRequirements({
  requirement,
  onUpdated,
}: RequirementLinkedRequirementsProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isAuthenticated = useIsAuthenticated();
  const canEdit = useCan(Capability.Requirement.UPDATE);
  const canCreate = useCan(Capability.Requirement.CREATE);
  const requirementId = requirement.id as UUID;
  const { refresh } = useRequirementActions(requirementId, onUpdated);

  const [children, setChildren] = useState<PickerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<PickerRow[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | undefined>();

  const fetchChildren = useCallback(async () => {
    setLoading(true);
    try {
      setChildren(
        await new RequirementClient().getChildRequirements(requirementId)
      );
    } catch {
      setChildren([]);
    } finally {
      setLoading(false);
    }
  }, [requirementId]);

  useEffect(() => {
    if (isAuthenticated) void fetchChildren();
  }, [isAuthenticated, fetchChildren]);

  const rows: LinkedRequirementRow[] = useMemo(
    () => [
      ...(requirement.parent
        ? [
            {
              id: String(requirement.parent.id),
              name: requirement.parent.name,
              description: '',
              relation: 'Parent' as const,
            },
          ]
        : []),
      ...children.map(child => ({
        id: String(child.id),
        name: child.name,
        description: child.description ?? '',
        relation: 'Child' as const,
      })),
    ],
    [requirement.parent, children]
  );

  /** Re-reads the children and the requirement, whose counts changed. */
  const reload = useCallback(
    async () => Promise.all([fetchChildren(), refresh()]),
    [fetchChildren, refresh]
  );

  const handleUnlink = useCallback(
    async (rowId: string) => {
      const row = rows.find(r => r.id === rowId);
      if (!row) return;
      try {
        const client = new RequirementClient();
        // A parent row unlinks this requirement; a child row unlinks the child.
        await client.updateRequirement(
          (row.relation === 'Parent' ? requirementId : row.id) as UUID,
          { parent_id: null }
        );
        await reload();
        notifications.show('Requirement unlinked', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to unlink requirement: ${error.message}`
            : 'Failed to unlink requirement',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [rows, requirementId, reload, notifications]
  );

  const columns = useMemo<GridColDef[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        renderCell: (params: GridRenderCellParams) => (
          <Box
            title={typeof params.value === 'string' ? params.value : ''}
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {typeof params.value === 'string' && params.value
              ? params.value
              : '—'}
          </Box>
        ),
      },
      {
        field: 'relation',
        headerName: 'Relation',
        width: 130,
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      createRowActionsColumn({
        canDelete: () => canEdit,
        onDelete: id => handleUnlink(id),
        deleteTooltip: 'Unlink',
        deleteIcon: LinkOffIcon,
      }),
    ],
    [canEdit, handleUnlink]
  );

  const drawerColumns = useMemo<GridColDef[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
      },
    ],
    []
  );

  const excluded = useMemo(
    () => new Set([String(requirementId), ...rows.map(r => r.id)]),
    [requirementId, rows]
  );

  const handleAssignClick = useCallback(async () => {
    setAssignOpen(true);
    setLoadingAvailable(true);
    try {
      const all = await new RequirementClient().getAllRequirements<
        PickerRow & { parent_id?: string | null }
      >({
        $select: 'id,name,description,parent_id',
        sort_by: 'name',
        sort_order: 'asc',
      });
      // Requirements nest one level deep: only a top-level requirement
      // without children of its own can become a child.
      const parents = new Set(
        all.flatMap(r => (r.parent_id ? [String(r.parent_id)] : []))
      );
      setAvailable(all.filter(r => !r.parent_id && !parents.has(String(r.id))));
    } catch {
      setAvailable([]);
    } finally {
      setLoadingAvailable(false);
    }
  }, []);

  const handleAssign = useCallback(
    async (selectedIds: string[]) => {
      const client = new RequirementClient();
      await Promise.all(
        selectedIds.map(id =>
          client.updateRequirement(id as UUID, { parent_id: requirementId })
        )
      );
      await reload();
      setAssignOpen(false);
    },
    [requirementId, reload]
  );

  const handleCreate = async (
    name: string,
    description: string,
    tagNames: string[],
    details: RequirementDetailsInput
  ) => {
    try {
      setCreating(true);
      setCreateError(undefined);
      const created = await new RequirementClient().createRequirement({
        name: name.trim(),
        description: description.trim() || null,
        organization_id: requirement.organization_id,
        ...details,
      });
      const tagsClient = new TagsClient();
      await Promise.all(
        tagNames.map(tagName =>
          tagsClient.assignTagToEntity(EntityType.REQUIREMENT, created.id, {
            name: tagName,
            organization_id: requirement.organization_id,
          })
        )
      );
      setCreateOpen(false);
      setAssignOpen(false);
      await reload();
    } catch {
      setCreateError('Failed to create the requirement. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const selfOption = useMemo(
    () => ({ id: requirementId, name: requirement.name }),
    [requirementId, requirement.name]
  );

  return (
    <>
      <LinkedEntitiesGrid
        title="Linked Requirements"
        rows={rows as unknown as GridRowModel[]}
        columns={columns}
        loading={loading}
        getRowId={row => String(row.id)}
        onRowClick={params => router.push(`/requirements/${String(params.id)}`)}
        // A child cannot hold children of its own.
        onAssignClick={
          canEdit && !requirement.parent ? handleAssignClick : undefined
        }
        searchPlaceholder="Search requirements…"
        emptyState={
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <AccountTreeOutlinedIcon
              sx={{ fontSize: 32, color: 'primary.main' }}
            />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No linked requirements yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              A requirement can hold narrower ones, like a policy and its rules.
              Click Assign to add children.
            </Typography>
          </Box>
        }
      />

      <AssignEntityDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign Child Requirements"
        rows={available.filter(r => !excluded.has(String(r.id)))}
        columns={drawerColumns}
        loading={loadingAvailable}
        getRowId={row => String(row.id)}
        onAssign={handleAssign}
        searchPlaceholder="Search requirements…"
        onCreateNew={canCreate ? () => setCreateOpen(true) : undefined}
        createNewLabel="Create new requirement"
      />

      <RequirementDrawer
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        name=""
        description=""
        initialParent={selfOption}
        onSave={handleCreate}
        isNew
        loading={creating}
        error={createError}
      />
    </>
  );
}
