"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import AccessDenied from "@/components/common/AccessDenied";
import { Can, useCan, useCanWithStatus } from "@/components/common/Can";
import { Capability } from "@/constants/capabilities";
import EntityEmptyState from "@/components/common/EntityEmptyState";
import { SectionCard } from "@/components/common/SectionCard";
import { useOrgSettings } from "@/contexts/OrgSettingsContext";
import { BORDER_RADIUS } from "@/styles/theme-constants";
import { fetchRoles } from "../api/role-cache";
import { getRoleChipSx } from "../role-display";
import type { RoleRead } from "../types";
import RoleEditorDrawer, { type DrawerMode } from "./RoleEditorDrawer";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function BuiltInRoleCard({
  role,
  onDetails,
}: {
  role: RoleRead;
  onDetails: () => void;
}) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        p: 2,
        border: (t) => `1px solid ${t.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        transition: "background 0.15s",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      <Box sx={{ width: 92, flexShrink: 0 }}>
        <Chip
          label={role.display_name}
          size="small"
          sx={{ ...getRoleChipSx(role), fontSize: 12, height: 24 }}
        />
      </Box>
      <Typography
        variant="body2"
        sx={{ flex: 1, color: "text.primary", lineHeight: 1.5 }}
      >
        {role.description}
      </Typography>
      <Button
        size="small"
        onClick={onDetails}
        sx={{ textTransform: "none", flexShrink: 0 }}
      >
        Details
      </Button>
    </Box>
  );
}

function PrivilegeRail() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 0.5,
        flexShrink: 0,
        width: 18,
      }}
    >
      <Typography
        sx={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "text.secondary",
          writingMode: "vertical-rl",
          whiteSpace: "nowrap",
          transform: "rotate(180deg)",
        }}
      >
        Most access
      </Typography>
      <Box
        sx={{
          width: 4,
          flex: 1,
          borderRadius: 1,
          background: (t) =>
            `linear-gradient(to bottom, ${t.palette.primary.main} 0%, ${t.palette.primary.light} 45%, ${t.palette.greyscale.border} 100%)`,
          my: 1,
        }}
      />
      <Typography
        sx={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "text.secondary",
          writingMode: "vertical-rl",
          whiteSpace: "nowrap",
        }}
      >
        Least access
      </Typography>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RolesTab() {
  const { sessionToken } = useOrgSettings();
  const { allowed: canReadRoles, loading: permsLoading } = useCanWithStatus(
    Capability.Role.READ,
  );
  const canManageRoles = useCan(Capability.Role.MANAGE);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>("view");
  const [selectedRole, setSelectedRole] = useState<RoleRead | undefined>();

  const loadRoles = useCallback(() => {
    fetchRoles(sessionToken)
      .then((data) => {
        setRoles(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load roles");
        setLoading(false);
      });
  }, [sessionToken]);

  useEffect(() => {
    if (permsLoading || !canReadRoles) return;
    loadRoles();
  }, [loadRoles, permsLoading, canReadRoles]);

  const openDrawer = useCallback((mode: DrawerMode, role?: RoleRead) => {
    setDrawerMode(mode);
    setSelectedRole(role);
    setDrawerOpen(true);
  }, []);

  const handleSaved = useCallback((saved: RoleRead) => {
    setRoles((prev) => {
      const idx = prev.findIndex((r) => r.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [...prev, saved];
    });
  }, []);

  const handleDeleted = useCallback((roleId: string) => {
    setRoles((prev) => prev.filter((r) => r.id !== roleId));
  }, []);

  if (permsLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!canReadRoles) {
    return <AccessDenied resource="roles" />;
  }

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Typography color="error" sx={{ p: 2 }}>
        {error}
      </Typography>
    );
  }

  const builtInRoles = roles
    .filter((r) => r.is_built_in)
    .sort((a, b) => b.level - a.level);

  const customRoles = roles.filter((r) => !r.is_built_in);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Built-in Roles */}
      <SectionCard
        title="Built-in Roles"
        subtitle="Five roles, ready to use. Permissions are fixed and cannot be changed."
      >
        <Box sx={{ display: "flex", gap: 2, alignItems: "stretch" }}>
          <PrivilegeRail />
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              gap: 1.25,
            }}
          >
            {builtInRoles.map((role) => (
              <BuiltInRoleCard
                key={role.id}
                role={role}
                onDetails={() => openDrawer("view", role)}
              />
            ))}
          </Box>
        </Box>
      </SectionCard>

      {/* Custom Roles */}
      <SectionCard
        title="Custom Roles"
        subtitle="Named roles for separation of duties. Common in regulated teams where built-in roles are not granular enough."
        actions={
          <Can capability={Capability.Role.MANAGE}>
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => openDrawer("create")}
              sx={{ textTransform: "none" }}
            >
              New role
            </Button>
          </Can>
        }
      >
        {customRoles.length === 0 ? (
          <EntityEmptyState
            icon={AdminPanelSettingsIcon}
            title="No custom roles yet"
            description="Create a custom role to define permissions that built-in roles do not cover."
            actionLabel={canManageRoles ? "New role" : undefined}
            onAction={canManageRoles ? () => openDrawer("create") : undefined}
            card
          />
        ) : (
          <TableContainer
            sx={{
              border: (t) => `1px solid ${t.palette.greyscale.border}`,
              borderRadius: BORDER_RADIUS.md,
              overflow: "hidden",
            }}
          >
            <Table size="small">
              <TableHead>
                <TableRow
                  sx={{
                    bgcolor: "action.hover",
                    "& th": {
                      fontWeight: 600,
                      fontSize: 14,
                      color: "text.primary",
                      borderBottom: (t) =>
                        `1px solid ${t.palette.greyscale.border}`,
                    },
                  }}
                >
                  <TableCell>Role</TableCell>
                  <TableCell>Purpose</TableCell>
                  <TableCell>Members</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {customRoles.map((role) => (
                  <TableRow
                    key={role.id}
                    sx={{
                      "&:hover": { bgcolor: "action.hover" },
                      "&:last-child td": { borderBottom: "none" },
                    }}
                  >
                    <TableCell>
                      <Chip
                        label={role.display_name}
                        size="small"
                        sx={{ ...getRoleChipSx(role), fontSize: 12 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {role.permissions.length} permissions
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {role.member_count}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        onClick={() => openDrawer("edit", role)}
                        sx={{ textTransform: "none" }}
                      >
                        Edit
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </SectionCard>

      {/* Role editor drawer */}
      <RoleEditorDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode={drawerMode}
        role={selectedRole}
        roles={roles}
        onSaved={handleSaved}
        onDeleted={handleDeleted}
      />
    </Box>
  );
}
