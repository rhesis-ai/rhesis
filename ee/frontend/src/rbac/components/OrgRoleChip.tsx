"use client";

import React, { useCallback, useEffect, useState } from "react";
import { MenuItem, Select, SelectChangeEvent, Skeleton, Typography } from "@mui/material";
import { useCan } from "@/components/common/Can";
import { Capability } from "@/constants/capabilities";
import { useFeature } from "@/contexts/FeaturesContext";
import { FeatureName } from "@/constants/features";
import { RbacClient } from "../api/rbac-client";
import { fetchRoles } from "../api/role-cache";
import {
  fetchOrgMembers,
  invalidateOrgMembers,
  getCachedOrgMembers,
} from "../api/org-members-cache";
import { isAssignableOrgRole, isWithinActorAuthority } from "../role-display";
import { useActorAuthority } from "../hooks/useActorAuthority";
import type { OrgMemberRead, RoleRead } from "../types";

// ---------------------------------------------------------------------------
// Props
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
  const [members, setMembers] = useState<OrgMemberRead[]>(getCachedOrgMembers());
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(getCachedOrgMembers().length === 0);
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

  const { level: myLevel, permissionNames: myPermissions } = useActorAuthority(
    sessionToken,
    "org",
  );
  const member = members.find((m) => m.user_id === userId);
  const assignableRoles = roles.filter(
    (r) => isAssignableOrgRole(r) && isWithinActorAuthority(r, myLevel, myPermissions),
  );

  const handleChange = useCallback(
    async (e: SelectChangeEvent<string>) => {
      const roleId = e.target.value;
      if (!roleId || roleId === member?.role_id) return;
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
    return <Skeleton variant="rounded" width={110} height={32} />;
  }

  return (
    <Select
      value={member?.role_id ?? ""}
      onChange={handleChange}
      disabled={!canManage || assigning}
      size="small"
      displayEmpty
      renderValue={(selected) => {
        if (!selected) {
          return (
            <Typography variant="body2" color="text.disabled">
              Assign role
            </Typography>
          );
        }
        // Use the full roles list so non-assignable roles (e.g. Owner) still
        // display their name rather than falling back to the raw UUID.
        const role = roles.find((r) => r.id === selected);
        return role?.display_name ?? selected;
      }}
      sx={{ minWidth: 120, fontSize: 13 }}
    >
      {assignableRoles.map((role) => (
        <MenuItem key={role.id} value={role.id}>
          {role.display_name}
        </MenuItem>
      ))}
    </Select>
  );
}
