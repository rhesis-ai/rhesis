import { type Page } from '@playwright/test';
import rolesFixture from '../fixtures/roles.json';
import orgMembersFixture from '../fixtures/org-members.json';

type JsonRecord = Record<string, unknown>;

function permissionFromName(name: string): JsonRecord {
  const [resourceType, action = ''] = name.split(':');
  return {
    id: name,
    name,
    display_name: name,
    resource_type: resourceType,
    action,
    scope: 'project',
    is_retired: false,
  };
}

/**
 * Mocks the `/rbac/*` EE endpoints (ee/backend/.../rbac/router.py) plus the
 * two ambient checks the RBAC UI depends on (`GET /features`,
 * `GET /me/permissions`) — none of which the base `mock-backend.mjs` server
 * or `MockApiHelper` know about, since RBAC ships dark by default.
 *
 * `mockRolesCrud()` keeps an in-memory copy of the roles list so a
 * create/edit/delete flow within one test sees its own writes reflected on
 * the next read, mirroring the real backend's request/response cycle.
 */
export class RbacMockHelper {
  constructor(private readonly page: Page) {}

  /**
   * Turn the RBAC feature flag on for this session.
   *
   * Wire shape is `{license: {edition, licensed}, enabled: string[]}`
   * (`FeaturesResponse` in `utils/api-client/features-client.ts`) — note this
   * differs from mock-backend.mjs's own default `/features` handler, whose
   * `{features: [], license: {tier}}` shape doesn't match `FeaturesResponse`
   * either, silently resolving to zero enabled features either way.
   */
  async mockFeaturesEnabled() {
    await this.page.route('**/features**', route => {
      if (route.request().method() !== 'GET') return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          enabled: ['rbac'],
          license: { edition: 'enterprise', licensed: true },
        }),
      });
    });
  }

  /** Grant the caller the given ambient capabilities via GET /me/permissions. */
  async mockPermissions(permittedActions: string[]) {
    await this.page.route('**/me/permissions**', route => {
      if (route.request().method() !== 'GET') return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(permittedActions),
      });
    });
  }

  /** Org-level role assignments — drives useActorAuthority and OrgRoleChip. */
  async mockOrganizationMembers(members: JsonRecord[] = orgMembersFixture) {
    await this.page.route('**/rbac/organization-members**', route => {
      if (route.request().method() !== 'GET') return route.fallback();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(members),
      });
    });
  }

  /**
   * Stateful GET/POST /rbac/roles and PUT/DELETE /rbac/roles/{id}.
   * Registers the detail route after the list route so the more specific
   * pattern is tried second — matching MockApiHelper's LIFO-priority
   * convention — though the two regexes are already mutually exclusive.
   */
  async mockRolesCrud(initialRoles: JsonRecord[] = rolesFixture) {
    const roles: JsonRecord[] = initialRoles.map(r => ({ ...r }));
    let nextId = 1;

    await this.page.route(/\/rbac\/roles(\?|$)/, async route => {
      const method = route.request().method();
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(roles),
        });
      }
      if (method === 'POST') {
        const body = route.request().postDataJSON() as JsonRecord;
        const permissionNames = (body.permission_names as string[]) ?? [];
        const created: JsonRecord = {
          description: '',
          scope: 'organization',
          ...body,
          id: `e2e-role-${nextId++}`,
          is_built_in: false,
          organization_id: 'e2e00000-0000-0000-0000-000000000002',
          member_count: 0,
          permissions: permissionNames.map(permissionFromName),
        };
        roles.push(created);
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(created),
        });
      }
      return route.fallback();
    });

    await this.page.route(/\/rbac\/roles\/[^/?]+(\?|$)/, async route => {
      const method = route.request().method();
      const id = new URL(route.request().url()).pathname
        .split('/')
        .filter(Boolean)
        .pop();
      const index = roles.findIndex(r => r.id === id);

      if (method === 'PUT') {
        if (index < 0) {
          return route.fulfill({
            status: 404,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Role not found' }),
          });
        }
        const body = route.request().postDataJSON() as JsonRecord;
        const permissionNames = body.permission_names as
          | string[]
          | undefined;
        roles[index] = {
          ...roles[index],
          ...body,
          ...(permissionNames
            ? { permissions: permissionNames.map(permissionFromName) }
            : {}),
        };
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(roles[index]),
        });
      }
      if (method === 'DELETE') {
        if (index >= 0) roles.splice(index, 1);
        return route.fulfill({ status: 204, contentType: 'application/json', body: '' });
      }
      return route.fallback();
    });
  }
}
