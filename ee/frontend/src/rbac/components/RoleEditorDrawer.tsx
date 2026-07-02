"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import BaseDrawer from "@/components/common/BaseDrawer";
import { drawerOutlinedFieldSx } from "@/components/common/drawerFormFieldSx";
import { useOrgSettings } from "@/contexts/OrgSettingsContext";
import { RbacClient } from "../api/rbac-client";
import type { RoleRead } from "../types";
import {
  CapabilityLevel,
  RESOURCE_AREAS,
  applyLevel,
  levelForArea,
} from "../capability-groups";
import PermissionGroupControl from "./PermissionGroupControl";
import RoleSummary from "./RoleSummary";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DrawerMode = "view" | "create" | "edit";

export interface RoleEditorDrawerProps {
  open: boolean;
  onClose: () => void;
  mode: DrawerMode;
  role?: RoleRead;
  roles?: RoleRead[];
  onSaved?: (role: RoleRead) => void;
  onDeleted?: (roleId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RoleEditorDrawer({
  open,
  onClose,
  mode,
  role,
  roles = [],
  onSaved,
  onDeleted,
}: RoleEditorDrawerProps) {
  const { sessionToken } = useOrgSettings();
  const readOnly = mode === "view";
  const isCreate = mode === "create";

  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [permissions, setPermissions] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  // Reset form when drawer opens or role changes
  useEffect(() => {
    if (!open) return;
    setError(undefined);
    setSubmitting(false);
    if (role && !isCreate) {
      setDisplayName(role.display_name);
      setDescription("");
      setPermissions(new Set(role.permissions.map((p) => p.name)));
    } else {
      setDisplayName("");
      setDescription("");
      setPermissions(new Set());
    }
  }, [open, role, isCreate]);

  const handleLevelChange = useCallback(
    (area: (typeof RESOURCE_AREAS)[number], level: CapabilityLevel) => {
      setPermissions((prev) => {
        const next = new Set(prev);
        applyLevel(next, area, level);
        return next;
      });
    },
    [],
  );

  const handleToggleCapability = useCallback((cap: string) => {
    setPermissions((prev) => {
      const next = new Set(prev);
      if (next.has(cap)) {
        next.delete(cap);
      } else {
        next.add(cap);
      }
      return next;
    });
  }, []);

  const handleCopyFrom = useCallback(
    (roleId: string) => {
      const source = roles.find((r) => r.id === roleId);
      if (source) {
        setPermissions(new Set(source.permissions.map((p) => p.name)));
      }
    },
    [roles],
  );

  const canSave = !submitting && displayName.trim().length > 0 && !readOnly;

  const handleSave = async () => {
    if (!canSave) return;
    setSubmitting(true);
    setError(undefined);
    const client = new RbacClient(sessionToken);

    try {
      let saved: RoleRead;
      if (isCreate) {
        saved = await client.createRole({
          name: displayName.trim().toLowerCase().replace(/\s+/g, "_"),
          display_name: displayName.trim(),
          permission_names: [...permissions],
        });
      } else if (role) {
        saved = await client.updateRole(role.id, {
          display_name: displayName.trim(),
          permission_names: [...permissions],
        });
      } else {
        return;
      }
      onSaved?.(saved);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save role");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!role || readOnly || role.is_built_in) return;
    setSubmitting(true);
    setError(undefined);
    const client = new RbacClient(sessionToken);

    try {
      await client.deleteRole(role.id);
      onDeleted?.(role.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete role");
    } finally {
      setSubmitting(false);
    }
  };

  const title = isCreate
    ? "Create Custom Role"
    : readOnly
      ? (role?.display_name ?? "Role Details")
      : `Edit ${role?.display_name ?? "Role"}`;

  const copyFromRoles = roles.filter(
    (r) => r.is_built_in && r.name !== "owner" && r.name !== "none",
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      onSave={readOnly ? undefined : handleSave}
      saveButtonText={
        submitting ? "Saving..." : isCreate ? "Create role" : "Save changes"
      }
      saveDisabled={!canSave}
      loading={submitting}
      error={error}
      closeButtonText={readOnly ? "Close" : "Cancel"}
      onDelete={
        !readOnly && !isCreate && role && !role.is_built_in
          ? handleDelete
          : undefined
      }
      deleteButtonText="Delete role"
    >
      {/* Role name and description */}
      {!readOnly && (
        <Stack spacing={2.5}>
          <TextField
            label="Role name"
            placeholder="e.g. QA Engineer"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            fullWidth
            sx={drawerOutlinedFieldSx}
          />

          {isCreate && copyFromRoles.length > 0 && (
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 0.5, display: "block" }}
              >
                Starts blank. Optionally copy from:
              </Typography>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                {copyFromRoles.map((r) => (
                  <Button
                    key={r.id}
                    size="small"
                    variant="text"
                    onClick={() => handleCopyFrom(r.id)}
                    sx={{ textTransform: "none", fontWeight: 500 }}
                  >
                    {r.display_name}
                  </Button>
                ))}
              </Box>
            </Box>
          )}

          <TextField
            label="Description"
            placeholder="What is this role for?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            minRows={2}
            fullWidth
            sx={drawerOutlinedFieldSx}
          />
        </Stack>
      )}

      {/* Read-only header for built-in roles */}
      {readOnly && role && (
        <Box>
          <Typography variant="body2" color="text.secondary">
            {role.is_built_in ? "Built-in role" : "Custom role"} ·{" "}
            {role.permissions.length} permissions
          </Typography>
        </Box>
      )}

      {/* Access by area */}
      <Box>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            mb: 1.5,
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Access by area
          </Typography>
          <Typography variant="caption" color="text.secondary">
            View = read · Edit = read + write · Manage = full control
          </Typography>
        </Box>
        <Stack spacing={1.5}>
          {RESOURCE_AREAS.map((area) => (
            <PermissionGroupControl
              key={area.id}
              area={area}
              currentLevel={levelForArea(permissions, area)}
              onLevelChange={(lvl) => handleLevelChange(area, lvl)}
              permissions={permissions}
              onToggleCapability={handleToggleCapability}
              readOnly={readOnly}
            />
          ))}
        </Stack>
      </Box>

      {/* Live summary */}
      <RoleSummary permissions={permissions} />
    </BaseDrawer>
  );
}
