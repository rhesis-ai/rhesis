"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Chip,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Skeleton,
  Typography,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import { useCan } from "@/components/common/Can";
import { Capability } from "@/constants/capabilities";
import { useFeature } from "@/contexts/FeaturesContext";
import { FeatureName } from "@/constants/features";
import { RbacClient } from "../api/rbac-client";
import { fetchRoles } from "../api/role-cache";
import { getRoleChipSx, isAssignableOrgRole } from "../role-display";
import type { OrgMemberRead, RoleRead } from "../types";

// ---------------------------------------------------------------------------
// Module-level cache — shared across all OrgRoleChip instances so only one
// fetch fires per grid render cycle.
// ---------------------------------------------------------------------------

interface CacheEntry<T> {
  key: string;
  data: T;
  ts: number;
}

let _membersCache: CacheEntry<OrgMemberRead[]> | null = null;
let _membersPending: Promise<OrgMemberRead[]> | null = null;

function fetchOrgMembers(sessionToken: string): Promise<OrgMemberRead[]> {
  if (
    _membersCache &&
    _membersCache.key === sessionToken &&
    Date.now() - _membersCache.ts < 30_000
  ) {
    return Promise.resolve(_membersCache.data);
  }
  if (_membersPending) return _membersPending;

  _membersPending = new RbacClient(sessionToken)
    .getOrganizationMembers()
    .then((data) => {
      _membersCache = { key: sessionToken, data, ts: Date.now() };
      _membersPending = null;
      return data;
    })
    .catch((err) => {
      _membersPending = null;
      throw err;
    });
  return _membersPending;
}

function invalidateOrgMembers() {
  _membersCache = null;
}

// ---------------------------------------------------------------------------
// Props & styling
// ---------------------------------------------------------------------------

interface OrgRoleChipProps {
  userId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
}


// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrgRoleChip({
  userId,
  sessionToken,
  onRoleChanged,
}: OrgRoleChipProps) {
  const rbacEnabled = useFeature(FeatureName.RBAC);
  const canManage = useCan(Capability.Member.MANAGE);
  const [members, setMembers] = useState<OrgMemberRead[]>(
    _membersCache?.data ?? [],
  );
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(!_membersCache);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    fetchOrgMembers(sessionToken).then((data) => {
      if (!cancelled) {
        setMembers(data);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (!rbacEnabled || !sessionToken || !canManage) return;
    let cancelled = false;
    fetchRoles(sessionToken)
      .then((data) => {
        if (!cancelled) setRoles(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [rbacEnabled, sessionToken, canManage]);

  const member = members.find((m) => m.user_id === userId);
  const currentRole = member?.role;

  const assignableRoles = roles.filter(isAssignableOrgRole);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      if (canManage && !assigning) setAnchorEl(e.currentTarget);
    },
    [canManage, assigning],
  );

  const handleClose = useCallback(() => setAnchorEl(null), []);

  const handleAssign = useCallback(
    async (roleId: string) => {
      setAnchorEl(null);
      if (roleId === member?.role_id) return;
      setAssigning(true);
      try {
        const client = new RbacClient(sessionToken);
        await client.assignOrgRole(userId, { role_id: roleId });
        invalidateOrgMembers();
        const fresh = await fetchOrgMembers(sessionToken);
        setMembers(fresh);
        onRoleChanged?.();
      } finally {
        setAssigning(false);
      }
    },
    [sessionToken, userId, member?.role_id, onRoleChanged],
  );

  if (loading) {
    return <Skeleton variant="rounded" width={80} height={24} />;
  }

  if (!currentRole) {
    return (
      <Typography variant="body2" color="text.secondary">
        —
      </Typography>
    );
  }

  const chipSx = getRoleChipSx(currentRole);

  return (
    <>
      <Chip
        label={currentRole.display_name}
        size="small"
        onClick={canManage ? handleClick : undefined}
        sx={{
          ...chipSx,
          fontSize: 12,
          height: 24,
          cursor: canManage ? "pointer" : "default",
          opacity: assigning ? 0.6 : 1,
        }}
      />
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        slotProps={{
          paper: { sx: { minWidth: 180, maxHeight: 300 } },
        }}
      >
        {assignableRoles.map((role) => (
          <MenuItem
            key={role.id}
            selected={role.id === member?.role_id}
            onClick={() => handleAssign(role.id)}
          >
            <ListItemText>
              <Typography variant="body2">{role.display_name}</Typography>
            </ListItemText>
            {role.id === member?.role_id && (
              <ListItemIcon sx={{ minWidth: "auto", ml: 1 }}>
                <CheckIcon fontSize="small" color="primary" />
              </ListItemIcon>
            )}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
