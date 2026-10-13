/**
 * Graded permission model for the role editor.
 *
 * This is an EE concern — community is binary owner/member with no
 * graded roles. Core ships only the flat `Capability` constants and
 * `CAPABILITY_LABELS`; all area grouping, level derivation, and
 * level-to-capability mapping lives here.
 *
 * The four capability levels (None → View → Edit → Manage) are
 * cumulative: Edit includes every capability from View, Manage
 * includes every capability from Edit. Each `ResourceArea` declares
 * the capability set at each level; the helpers below derive the
 * current level from an arbitrary permission set and vice versa.
 */

import { CAPABILITY_LABELS } from '@/constants/capabilities';
import {
  CapabilityLevel,
  RESOURCE_AREAS,
  RESOURCE_DISPLAY_NAMES,
  RESOURCE_ORDER_BY_AREA,
  type ResourceArea,
} from '../shared/resource-catalog';

// Areas and names live in the shared catalog, which the audit log reads too.
export { CapabilityLevel, RESOURCE_AREAS, type ResourceArea };

// ---------------------------------------------------------------------------
// Capability levels
// ---------------------------------------------------------------------------

export const LEVEL_LABELS: Record<CapabilityLevel, string> = {
  [CapabilityLevel.NONE]: 'None',
  [CapabilityLevel.VIEW]: 'View',
  [CapabilityLevel.EDIT]: 'Edit',
  [CapabilityLevel.MANAGE]: 'Manage',
};

export const LEVEL_DESCRIPTIONS: Record<CapabilityLevel, string> = {
  [CapabilityLevel.NONE]: 'No access',
  [CapabilityLevel.VIEW]: 'Read-only',
  [CapabilityLevel.EDIT]: 'Read, write, and delete own',
  [CapabilityLevel.MANAGE]: 'Full control',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Return the highest `CapabilityLevel` whose full capability set is
 * present in `permissions`. Levels are cumulative, so if all VIEW
 * capabilities exist but not all EDIT ones, this returns VIEW.
 */
export function levelForArea(
  permissions: ReadonlySet<string>,
  area: ResourceArea
): CapabilityLevel {
  for (let lvl = CapabilityLevel.MANAGE; lvl > CapabilityLevel.NONE; lvl--) {
    const required = area.levels[lvl as CapabilityLevel];
    if (required.length > 0 && required.every(c => permissions.has(c))) {
      return lvl as CapabilityLevel;
    }
  }
  return CapabilityLevel.NONE;
}

/**
 * Compute per-area levels for a permission set. Returns a map of
 * `area.id → CapabilityLevel`.
 */
export function groupCapabilities(
  permissions: ReadonlySet<string>
): Record<string, CapabilityLevel> {
  const result: Record<string, CapabilityLevel> = {};
  for (const area of RESOURCE_AREAS) {
    result[area.id] = levelForArea(permissions, area);
  }
  return result;
}

/**
 * Apply a level selection for one area to a mutable permission set.
 * Removes all capabilities from the area's level definitions, then
 * adds the capabilities for the target level.
 */
export function applyLevel(
  permissions: Set<string>,
  area: ResourceArea,
  level: CapabilityLevel
): Set<string> {
  const allInArea = new Set(Object.values(area.levels).flatMap(caps => caps));
  for (const cap of allInArea) {
    permissions.delete(cap);
  }
  for (const cap of area.levels[level]) {
    permissions.add(cap);
  }
  return permissions;
}

/**
 * Generate plain-language summary sentences for the current permission set.
 */
export function summarizePermissions(permissions: ReadonlySet<string>): {
  granted: string[];
  denied: string[];
} {
  const granted: string[] = [];
  const denied: string[] = [];

  for (const area of RESOURCE_AREAS) {
    const level = levelForArea(permissions, area);
    if (level === CapabilityLevel.NONE) {
      denied.push(`No access to ${area.label.toLowerCase()}`);
    } else {
      const desc = LEVEL_DESCRIPTIONS[level];
      granted.push(`${area.label}: ${desc.toLowerCase()}`);
    }
  }

  return { granted, denied };
}

/**
 * Return the human label for a capability string, falling back to
 * the raw string if no label is registered.
 */
export function capabilityLabel(cap: string): string {
  return CAPABILITY_LABELS[cap] ?? cap;
}

// ---------------------------------------------------------------------------
// Per-resource permission rows (role editor detail view)
// ---------------------------------------------------------------------------

export interface ResourcePermissionRow {
  resourceId: string;
  label: string;
  view?: string;
  create?: string;
  editOwn?: string;
  editAll?: string;
  deleteOwn?: string;
  deleteAll?: string;
  /** Non-column capabilities (generate, execute, manage, assigned, …). */
  extras: { cap: string; label: string }[];
}

function capsInArea(area: ResourceArea): string[] {
  return [...new Set(Object.values(area.levels).flatMap(caps => [...caps]))];
}

/** `resource:update` / `resource:delete` → matching `:own` capability string. */
export function getOwnImpliedByAllCap(allCap: string): string | undefined {
  const match = allCap.match(/^([^:]+):(update|delete)$/);
  if (!match) return undefined;
  return `${match[1]}:${match[2]}:own`;
}

/** `resource:update:own` / `resource:delete:own` → matching unscoped capability. */
export function getAllCapImplyingOwn(ownCap: string): string | undefined {
  const match = ownCap.match(/^([^:]+):(update|delete):own$/);
  if (!match) return undefined;
  return `${match[1]}:${match[2]}`;
}

export function isOwnCapImpliedByAll(
  permissions: ReadonlySet<string>,
  ownCap: string,
  availableCaps: ReadonlySet<string>
): boolean {
  const allCap = getAllCapImplyingOwn(ownCap);
  if (!allCap || !availableCaps.has(allCap)) return false;
  return permissions.has(allCap);
}

/**
 * Toggle one capability in a set. Selecting an "all" edit/delete cap also
 * grants the matching ":own" cap; clearing "all" clears ":own" too.
 */
export function applyCapabilityToggle(
  permissions: Set<string>,
  cap: string,
  availableCaps: ReadonlySet<string>
): void {
  const ownImplied = getOwnImpliedByAllCap(cap);
  const validOwnImplied =
    ownImplied && availableCaps.has(ownImplied) ? ownImplied : undefined;

  if (permissions.has(cap)) {
    permissions.delete(cap);
    if (validOwnImplied) permissions.delete(validOwnImplied);
    return;
  }

  permissions.add(cap);
  if (validOwnImplied) permissions.add(validOwnImplied);
}

export function areaCapabilitySet(area: ResourceArea): ReadonlySet<string> {
  return new Set(capsInArea(area));
}

function standardCap(
  caps: string[],
  resourceId: string,
  action: string
): string | undefined {
  const target = `${resourceId}:${action}`;
  return caps.find(cap => cap === target);
}

function scopedCap(
  caps: string[],
  resourceId: string,
  action: string,
  scope: string
): string | undefined {
  const target = `${resourceId}:${action}:${scope}`;
  return caps.find(cap => cap === target);
}

function extraCapabilityLabel(cap: string): string {
  return capabilityLabel(cap);
}

/**
 * Group an area's capabilities into per-resource rows with View/Create and
 * scoped Edit/Delete columns plus any additional permission checkboxes.
 */
export function groupAreaCapabilitiesByResource(
  area: ResourceArea
): ResourcePermissionRow[] {
  const allCaps = capsInArea(area);
  const byResource = new Map<string, string[]>();

  for (const cap of allCaps) {
    const resourceId = cap.split(':')[0] ?? cap;
    const list = byResource.get(resourceId) ?? [];
    list.push(cap);
    byResource.set(resourceId, list);
  }

  const order = RESOURCE_ORDER_BY_AREA[area.id] ?? [];
  const resourceIds = [
    ...order.filter(id => byResource.has(id)),
    ...[...byResource.keys()]
      .filter(id => !order.includes(id))
      .sort((a, b) => a.localeCompare(b)),
  ];

  return resourceIds.map(resourceId => {
    const caps = byResource.get(resourceId) ?? [];
    const label = RESOURCE_DISPLAY_NAMES[resourceId] ?? resourceId;
    const view = standardCap(caps, resourceId, 'read');
    const create = standardCap(caps, resourceId, 'create');
    const editOwn = scopedCap(caps, resourceId, 'update', 'own');
    const editAll = standardCap(caps, resourceId, 'update');
    const deleteOwn = scopedCap(caps, resourceId, 'delete', 'own');
    const deleteAll = standardCap(caps, resourceId, 'delete');
    const columnCaps = new Set(
      [view, create, editOwn, editAll, deleteOwn, deleteAll].filter(
        (cap): cap is string => Boolean(cap)
      )
    );
    const extras = caps
      .filter(cap => !columnCaps.has(cap))
      .map(cap => ({
        cap,
        label: extraCapabilityLabel(cap),
      }))
      .sort((a, b) => a.label.localeCompare(b.label));

    return {
      resourceId,
      label,
      view,
      create,
      editOwn,
      editAll,
      deleteOwn,
      deleteAll,
      extras,
    };
  });
}
