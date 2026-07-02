"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  alpha,
  Chip,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Skeleton,
  Typography,
} from "@mui/material";
import type { Theme } from "@mui/material/styles";
import CheckIcon from "@mui/icons-material/Check";
import { useCan } from "@/components/common/Can";
import { Capability } from "@/constants/capabilities";
import { useFeature } from "@/contexts/FeaturesContext";
import { FeatureName } from "@/constants/features";
import { GREYSCALE } from "@/styles/theme-constants";
import { fetchRoles } from "../api/role-cache";
import type { ProjectMemberRoleRead, RoleRead } from "../types";

// ---------------------------------------------------------------------------
// Module-level cache per project
// ---------------------------------------------------------------------------

interface CacheEntry<T> {
  data: T;
  ts: number;
}

const _projectMembersCache = new Map<
  string,
  CacheEntry<ProjectMemberRoleRead[]>
>();
const _projectMembersPending = new Map<
  string,
  Promise<ProjectMemberRoleRead[]>
>();

function fetchProjectMembers(
  sessionToken: string,
  projectId: string,
): Promise<ProjectMemberRoleRead[]> {
  const cached = _projectMembersCache.get(projectId);
  if (cached && Date.now() - cached.ts < 30_000) {
    return Promise.resolve(cached.data);
  }
  const pending = _projectMembersPending.get(projectId);
  if (pending) return pending;

  const promise = new RbacClient(sessionToken)
    .getProjectMembers(projectId)
    .then((data) => {
      _projectMembersCache.set(projectId, { data, ts: Date.now() });
      _projectMembersPending.delete(projectId);
      return data;
    })
    .catch((err) => {
      _projectMembersPending.delete(projectId);
      throw err;
    });
  _projectMembersPending.set(projectId, promise);
  return promise;
}

function invalidateProjectMembers(projectId: string) {
  _projectMembersCache.delete(projectId);
}

// ---------------------------------------------------------------------------
// Props & styling
// ---------------------------------------------------------------------------

interface ProjectRoleChipProps {
  userId: string;
  projectId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
}

const ROLE_CHIP_SX: Record<string, Record<string, unknown>> = {
  admin: {
    bgcolor: (t: Theme) => alpha(t.palette.primary.light, 0.13),
    color: "primary.dark",
    fontWeight: 600,
  },
  member: {
    bgcolor: (t: Theme) => alpha(t.palette.primary.light, 0.08),
    color: "primary.main",
  },
  viewer: {
    bgcolor: GREYSCALE.light.surface2,
    color: GREYSCALE.light.label,
  },
  none: {
    bgcolor: "transparent",
    color: GREYSCALE.light.subtitle,
    border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProjectRoleChip({
  userId,
  projectId,
  sessionToken,
  onRoleChanged,
}: ProjectRoleChipProps) {
  const rbacEnabled = useFeature(FeatureName.RBAC);
  const canManage = useCan(Capability.ProjectMember.MANAGE);
  const [members, setMembers] = useState<ProjectMemberRoleRead[]>(
    _projectMembersCache.get(projectId)?.data ?? [],
  );
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(!_projectMembersCache.has(projectId));
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!sessionToken || !projectId) return;
    let cancelled = false;
    fetchProjectMembers(sessionToken, projectId)
      .then((data) => {
        if (!cancelled) {
          setMembers(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken, projectId]);

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

  const memberEntry = members.find((m) => m.user_id === userId);
  const currentRole = memberEntry?.role;

  const assignableRoles = roles.filter(
    (r) => !r.is_built_in || (r.name !== "owner" && r.name !== "none"),
  );

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
      if (roleId === memberEntry?.role_id) return;
      setAssigning(true);
      try {
        const client = new RbacClient(sessionToken);
        await client.assignProjectRole(projectId, userId, {
          role_id: roleId,
        });
        invalidateProjectMembers(projectId);
        const fresh = await fetchProjectMembers(sessionToken, projectId);
        setMembers(fresh);
        onRoleChanged?.();
      } finally {
        setAssigning(false);
      }
    },
    [sessionToken, projectId, userId, memberEntry?.role_id, onRoleChanged],
  );

  if (loading) {
    return <Skeleton variant="rounded" width={80} height={24} />;
  }

  if (!currentRole) {
    return (
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ textTransform: "capitalize" }}
      >
        member
      </Typography>
    );
  }

  const chipSx = ROLE_CHIP_SX[currentRole.name] ?? {
    bgcolor: (t: Theme) => alpha(t.palette.warning.main, 0.1),
    color: "warning.dark",
    fontWeight: 600,
  };

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
            selected={role.id === memberEntry?.role_id}
            onClick={() => handleAssign(role.id)}
          >
            <ListItemText>
              <Typography variant="body2">{role.display_name}</Typography>
            </ListItemText>
            {role.id === memberEntry?.role_id && (
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
