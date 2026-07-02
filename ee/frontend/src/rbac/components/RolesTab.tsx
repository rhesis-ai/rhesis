"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  alpha,
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
import type { Theme } from "@mui/material/styles";
import AddIcon from "@mui/icons-material/Add";
import { SectionCard } from "@/components/common/SectionCard";
import { useOrgSettings } from "@/contexts/OrgSettingsContext";
import { BORDER_RADIUS, GREYSCALE } from "@/styles/theme-constants";
import { RbacClient } from "../api/rbac-client";
import type { RoleRead } from "../types";
import RoleEditorDrawer, { type DrawerMode } from "./RoleEditorDrawer";

// ---------------------------------------------------------------------------
// Built-in role display metadata
// ---------------------------------------------------------------------------

interface RoleDisplayInfo {
  description: string;
  meta: string;
  chipSx: Record<string, unknown>;
}

const BUILT_IN_ROLE_DISPLAY: Record<string, RoleDisplayInfo> = {
  owner: {
    description:
      "Complete control of the organization, including billing, " +
      "deletion, and transferring ownership.",
    meta: "Every permission",
    chipSx: {
      bgcolor: "primary.main",
      color: "primary.contrastText",
      fontWeight: 600,
    },
  },
  admin: {
    description:
      "Manage members, roles, projects, and organization settings. " +
      "Cannot delete the organization.",
    meta: "All but org deletion",
    chipSx: {
      bgcolor: (t: Theme) => alpha(t.palette.primary.light, 0.13),
      color: "primary.dark",
      fontWeight: 600,
    },
  },
  member: {
    description:
      "Create, edit, and run evaluations across their projects. " +
      "Manage their own API tokens.",
    meta: "Read & write resources",
    chipSx: {
      bgcolor: (t: Theme) => alpha(t.palette.primary.light, 0.08),
      color: "primary.main",
    },
  },
  viewer: {
    description:
      "Read-only access to all resources. Can browse and export " +
      "but cannot make changes.",
    meta: "Read-only",
    chipSx: {
      bgcolor: GREYSCALE.light.surface2,
      color: GREYSCALE.light.label,
    },
  },
  none: {
    description:
      "No access. Explicitly revoke a member while keeping them " +
      "in the organization.",
    meta: "No permissions",
    chipSx: {
      bgcolor: "transparent",
      color: GREYSCALE.light.subtitle,
      border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
    },
  },
};

const BUILT_IN_ORDER = ["owner", "admin", "member", "viewer", "none"];

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
  const display = BUILT_IN_ROLE_DISPLAY[role.name] ?? {
    description: role.display_name,
    meta: `${role.permissions.length} permissions`,
    chipSx: {},
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        p: 2,
        border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        transition: "background 0.15s",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      <Box sx={{ width: 92, flexShrink: 0 }}>
        <Chip
          label={role.display_name}
          size="small"
          sx={{
            ...display.chipSx,
            fontSize: 12,
            height: 24,
          }}
        />
      </Box>
      <Typography
        variant="body2"
        sx={{ flex: 1, color: "text.primary", lineHeight: 1.5 }}
      >
        {display.description}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          width: 150,
          flexShrink: 0,
          textAlign: "right",
          color: "text.secondary",
        }}
      >
        {display.meta}
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
          background: (t: Theme) =>
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
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<DrawerMode>("view");
  const [selectedRole, setSelectedRole] = useState<RoleRead | undefined>();

  const loadRoles = useCallback(() => {
    const client = new RbacClient(sessionToken);
    client
      .getRoles()
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
    loadRoles();
  }, [loadRoles]);

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

  const builtInRoles = BUILT_IN_ORDER.map((name) =>
    roles.find((r) => r.is_built_in && r.name === name),
  ).filter((r): r is RoleRead => r != null);

  const customRoles = roles.filter((r) => !r.is_built_in);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Built-in Roles */}
      <SectionCard
        title="Built-in Roles"
        subtitle="Five roles, ready to use — this is what most teams need. Permissions are fixed."
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
        subtitle="For separation of duties — named roles built-ins can't express. Common in regulated teams."
        actions={
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => openDrawer("create")}
            sx={{ textTransform: "none" }}
          >
            New role
          </Button>
        }
      >
        {customRoles.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No custom roles yet. Create one to define permissions that built-in
            roles don&apos;t cover.
          </Typography>
        ) : (
          <TableContainer
            sx={{
              border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
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
                      borderBottom: (t: Theme) =>
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
                        sx={{
                          bgcolor: (t: Theme) =>
                            alpha(t.palette.warning.main, 0.1),
                          color: "warning.dark",
                          fontWeight: 600,
                          fontSize: 12,
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {role.permissions.length} permissions
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        —
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
