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

import { Capability, CAPABILITY_LABELS } from "@/constants/capabilities";

// ---------------------------------------------------------------------------
// Capability levels
// ---------------------------------------------------------------------------

export enum CapabilityLevel {
  NONE = 0,
  VIEW = 1,
  EDIT = 2,
  MANAGE = 3,
}

export const LEVEL_LABELS: Record<CapabilityLevel, string> = {
  [CapabilityLevel.NONE]: "None",
  [CapabilityLevel.VIEW]: "View",
  [CapabilityLevel.EDIT]: "Edit",
  [CapabilityLevel.MANAGE]: "Manage",
};

export const LEVEL_DESCRIPTIONS: Record<CapabilityLevel, string> = {
  [CapabilityLevel.NONE]: "No access",
  [CapabilityLevel.VIEW]: "Read-only",
  [CapabilityLevel.EDIT]: "Read, write, and delete own",
  [CapabilityLevel.MANAGE]: "Full control",
};

// ---------------------------------------------------------------------------
// Resource areas
// ---------------------------------------------------------------------------

export interface ResourceArea {
  id: string;
  label: string;
  description: string;
  levels: Record<CapabilityLevel, readonly string[]>;
}

export const RESOURCE_AREAS: readonly ResourceArea[] = [
  {
    id: "test-resources",
    label: "Test Resources",
    description: "Test sets, runs, experiments, endpoints",
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.TestSet.READ,
        Capability.Test.READ,
        Capability.TestConfiguration.READ,
        Capability.TestRun.READ,
        Capability.TestResult.READ,
        Capability.Experiment.READ,
        Capability.Endpoint.READ,
        Capability.Comment.READ,
        Capability.Task.READ,
      ],
      [CapabilityLevel.EDIT]: [
        Capability.TestSet.READ,
        Capability.TestSet.CREATE,
        Capability.TestSet.UPDATE,
        Capability.TestSet.GENERATE,
        Capability.Test.READ,
        Capability.Test.CREATE,
        Capability.Test.UPDATE,
        Capability.TestConfiguration.READ,
        Capability.TestConfiguration.CREATE,
        Capability.TestConfiguration.UPDATE,
        Capability.TestRun.READ,
        Capability.TestRun.CREATE,
        Capability.TestRun.UPDATE,
        Capability.TestRun.EXECUTE,
        Capability.TestRun.DELETE_OWN,
        Capability.TestResult.READ,
        Capability.TestResult.UPDATE_OWN,
        Capability.TestResult.DELETE_OWN,
        Capability.Experiment.READ,
        Capability.Experiment.CREATE,
        Capability.Experiment.UPDATE_OWN,
        Capability.Experiment.DELETE_OWN,
        Capability.Endpoint.READ,
        Capability.Endpoint.CREATE,
        Capability.Endpoint.UPDATE,
        Capability.Comment.READ,
        Capability.Comment.CREATE,
        Capability.Comment.REACT,
        Capability.Comment.UPDATE_OWN,
        Capability.Comment.DELETE_OWN,
        Capability.Task.READ,
        Capability.Task.CREATE,
        Capability.Task.UPDATE_OWN,
        Capability.Task.UPDATE_ASSIGNED,
        Capability.Task.DELETE_OWN,
        Capability.Preflight.CREATE,
      ],
      [CapabilityLevel.MANAGE]: [
        Capability.TestSet.READ,
        Capability.TestSet.CREATE,
        Capability.TestSet.UPDATE,
        Capability.TestSet.DELETE,
        Capability.TestSet.GENERATE,
        Capability.TestSet.EXECUTE,
        Capability.Test.READ,
        Capability.Test.CREATE,
        Capability.Test.UPDATE,
        Capability.Test.DELETE,
        Capability.TestConfiguration.READ,
        Capability.TestConfiguration.CREATE,
        Capability.TestConfiguration.UPDATE,
        Capability.TestConfiguration.DELETE,
        Capability.TestRun.READ,
        Capability.TestRun.CREATE,
        Capability.TestRun.UPDATE,
        Capability.TestRun.DELETE,
        Capability.TestRun.EXECUTE,
        Capability.TestRun.DELETE_OWN,
        Capability.TestResult.READ,
        Capability.TestResult.UPDATE,
        Capability.TestResult.DELETE,
        Capability.TestResult.UPDATE_OWN,
        Capability.TestResult.DELETE_OWN,
        Capability.Experiment.READ,
        Capability.Experiment.CREATE,
        Capability.Experiment.UPDATE,
        Capability.Experiment.DELETE,
        Capability.Experiment.UPDATE_OWN,
        Capability.Experiment.DELETE_OWN,
        Capability.Endpoint.READ,
        Capability.Endpoint.CREATE,
        Capability.Endpoint.UPDATE,
        Capability.Endpoint.DELETE,
        Capability.Comment.READ,
        Capability.Comment.CREATE,
        Capability.Comment.UPDATE,
        Capability.Comment.DELETE,
        Capability.Comment.REACT,
        Capability.Comment.UPDATE_OWN,
        Capability.Comment.DELETE_OWN,
        Capability.Task.READ,
        Capability.Task.CREATE,
        Capability.Task.UPDATE,
        Capability.Task.DELETE,
        Capability.Task.UPDATE_OWN,
        Capability.Task.UPDATE_ASSIGNED,
        Capability.Task.DELETE_OWN,
        Capability.Preflight.CREATE,
      ],
    },
  },
  {
    id: "observability",
    label: "Observability",
    description: "Traces, explorer sessions",
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.Telemetry.READ,
        Capability.Explorer.READ,
      ],
      [CapabilityLevel.EDIT]: [
        Capability.Telemetry.READ,
        Capability.Telemetry.CREATE,
        Capability.Telemetry.UPDATE,
        Capability.Explorer.READ,
        Capability.Explorer.CREATE,
        Capability.Explorer.UPDATE,
      ],
      [CapabilityLevel.MANAGE]: [
        Capability.Telemetry.READ,
        Capability.Telemetry.CREATE,
        Capability.Telemetry.UPDATE,
        Capability.Telemetry.DELETE,
        Capability.Explorer.READ,
        Capability.Explorer.CREATE,
        Capability.Explorer.UPDATE,
        Capability.Explorer.DELETE,
      ],
    },
  },
  {
    id: "infrastructure",
    label: "Infrastructure",
    description: "Models, metrics, knowledge, tools, files",
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.Model.READ,
        Capability.Metric.READ,
        Capability.Source.READ,
        Capability.Behavior.READ,
        Capability.Tool.READ,
        Capability.Architect.READ,
        Capability.File.READ,
      ],
      [CapabilityLevel.EDIT]: [
        Capability.Model.READ,
        Capability.Model.CREATE,
        Capability.Model.UPDATE,
        Capability.Metric.READ,
        Capability.Metric.CREATE,
        Capability.Metric.UPDATE,
        Capability.Source.READ,
        Capability.Source.CREATE,
        Capability.Source.UPDATE,
        Capability.Behavior.READ,
        Capability.Behavior.CREATE,
        Capability.Behavior.UPDATE,
        Capability.Tool.READ,
        Capability.Tool.CREATE,
        Capability.Tool.UPDATE,
        Capability.Architect.READ,
        Capability.Architect.CREATE,
        Capability.File.READ,
        Capability.File.CREATE,
        Capability.File.UPDATE,
        Capability.File.IMPORT,
      ],
      [CapabilityLevel.MANAGE]: [
        Capability.Model.READ,
        Capability.Model.CREATE,
        Capability.Model.UPDATE,
        Capability.Model.DELETE,
        Capability.Metric.READ,
        Capability.Metric.CREATE,
        Capability.Metric.UPDATE,
        Capability.Metric.DELETE,
        Capability.Source.READ,
        Capability.Source.CREATE,
        Capability.Source.UPDATE,
        Capability.Source.DELETE,
        Capability.Behavior.READ,
        Capability.Behavior.CREATE,
        Capability.Behavior.UPDATE,
        Capability.Behavior.DELETE,
        Capability.Tool.READ,
        Capability.Tool.CREATE,
        Capability.Tool.UPDATE,
        Capability.Tool.DELETE,
        Capability.Architect.READ,
        Capability.Architect.CREATE,
        Capability.Architect.DELETE,
        Capability.File.READ,
        Capability.File.CREATE,
        Capability.File.UPDATE,
        Capability.File.DELETE,
        Capability.File.IMPORT,
      ],
    },
  },
  {
    id: "administration",
    label: "Administration",
    description: "Members, projects, roles, tokens",
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.Organization.READ,
        Capability.Member.READ,
        Capability.Project.READ,
        Capability.Role.READ,
        Capability.Recycle.VIEW,
      ],
      [CapabilityLevel.EDIT]: [
        Capability.Organization.READ,
        Capability.Organization.UPDATE,
        Capability.Member.READ,
        Capability.Member.CREATE,
        Capability.Member.UPDATE,
        Capability.Project.READ,
        Capability.Project.CREATE,
        Capability.Project.UPDATE,
        Capability.ProjectMember.MANAGE,
        Capability.Role.READ,
        Capability.Recycle.VIEW,
        Capability.Recycle.RESTORE,
      ],
      [CapabilityLevel.MANAGE]: [
        Capability.Organization.READ,
        Capability.Organization.UPDATE,
        Capability.Member.READ,
        Capability.Member.CREATE,
        Capability.Member.UPDATE,
        Capability.Member.DELETE,
        Capability.Member.MANAGE,
        Capability.Project.READ,
        Capability.Project.CREATE,
        Capability.Project.UPDATE,
        Capability.ProjectMember.MANAGE,
        Capability.Role.READ,
        Capability.Role.MANAGE,
        Capability.Token.MANAGE,
        Capability.Recycle.VIEW,
        Capability.Recycle.RESTORE,
        Capability.Recycle.PURGE,
        Capability.SSO.MANAGE,
        Capability.ApiClients.MANAGE,
      ],
    },
  },
];

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
  area: ResourceArea,
): CapabilityLevel {
  for (let lvl = CapabilityLevel.MANAGE; lvl > CapabilityLevel.NONE; lvl--) {
    const required = area.levels[lvl as CapabilityLevel];
    if (required.length > 0 && required.every((c) => permissions.has(c))) {
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
  permissions: ReadonlySet<string>,
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
  level: CapabilityLevel,
): Set<string> {
  const allInArea = new Set(Object.values(area.levels).flatMap((caps) => caps));
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
