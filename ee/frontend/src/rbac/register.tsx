/**
 * RBAC feature registration.
 *
 * Plugs the Roles tab into core's organization-settings-tabs registry
 * and registers member role extension components for grids and drawers.
 * Mirrors `ee/frontend/src/sso/register.tsx` — each EE feature has a
 * sibling `register.ts(x)` so `bootstrap.ts` stays a one-line list.
 *
 * The `<FeatureGate>` is here (not in the page) because EE owns its
 * gating end-to-end. When RBAC is OFF, the fallback renders the
 * community empty state. When RBAC is ON, the actual Roles tab loads.
 */

import * as React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { FeatureName } from '@/constants/features';
import { FeatureGate } from '@/contexts/FeaturesContext';
import {
  registerOrgSettingsTab,
  registerMemberRoleExtensions,
  registerTokenScopeExtensions,
} from '@/lib/extension-registries';
import RolesEmptyState from './components/RolesEmptyState';
import OrgRoleChip from './components/OrgRoleChip';
import ProjectRoleChip from './components/ProjectRoleChip';
import RoleSelectField from './components/RoleSelectField';
import TokenScopeField from './components/TokenScopeField';
import { RbacClient } from './api/rbac-client';
import { fetchOrgMembers } from './api/org-members-cache';
import { fetchProjectMembers } from './api/project-members-cache';
import { fetchRoles } from './api/role-cache';

const RolesTab = React.lazy(() => import('./components/RolesTab'));

function RolesTabSection() {
  return (
    <FeatureGate feature={FeatureName.RBAC} fallback={<RolesEmptyState />}>
      <React.Suspense
        fallback={
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={24} />
          </Box>
        }
      >
        <RolesTab />
      </React.Suspense>
    </FeatureGate>
  );
}

export function registerRBAC(): void {
  registerOrgSettingsTab({
    id: 'roles',
    title: 'Roles',
    order: 150,
    component: RolesTabSection,
  });

  registerMemberRoleExtensions({
    OrgRoleCell: OrgRoleChip,
    ProjectRoleCell: ProjectRoleChip,
    AddMemberRoleField: RoleSelectField,
    assignProjectMemberRole: async (
      sessionToken: string,
      projectId: string,
      userId: string,
      roleId: string
    ) => {
      const client = new RbacClient(sessionToken);
      await client.assignProjectRole(projectId, userId, {
        role_id: roleId,
      });
    },
    fetchUserProjectMemberships: async (
      sessionToken: string,
      userId: string
    ) => {
      const client = new RbacClient(sessionToken);
      return client.getUserProjectMemberships(userId);
    },
    prewarmCaches: (sessionToken, opts) => {
      fetchOrgMembers(sessionToken);
      if (opts?.canManageRoles) {
        fetchRoles(sessionToken);
      }
    },
    prewarmProjectCaches: (sessionToken, projectId, opts) => {
      fetchProjectMembers(sessionToken, projectId);
      if (opts?.canManageRoles) {
        fetchRoles(sessionToken);
      }
    },
  });

  registerTokenScopeExtensions({
    TokenScopeField,
  });
}
