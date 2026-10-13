/**
 * The resource vocabulary EE screens share: which area a resource belongs
 * to, and what it is called on screen.
 *
 * The role editor groups capabilities by these areas. The audit log uses the
 * same areas for its category chips and the same names for its action labels
 * ("Endpoint updated"), so the two screens never word a resource differently.
 */

import { Capability } from '@/constants/capabilities';

// ---------------------------------------------------------------------------
// Capability levels
// ---------------------------------------------------------------------------

export enum CapabilityLevel {
  NONE = 0,
  VIEW = 1,
  EDIT = 2,
  MANAGE = 3,
}

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
    id: 'test-resources',
    label: 'Test Resources',
    description: 'Test sets, runs, experiments, endpoints',
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
        Capability.Garak.READ,
        Capability.Owasp.READ,
      ],
      [CapabilityLevel.EDIT]: [
        Capability.TestSet.READ,
        Capability.TestSet.CREATE,
        Capability.TestSet.UPDATE,
        Capability.TestSet.GENERATE,
        Capability.TestSet.EXECUTE,
        Capability.TestSet.EXPORT,
        Capability.Test.READ,
        Capability.Test.CREATE,
        Capability.Test.UPDATE,
        Capability.Garak.READ,
        Capability.Garak.CREATE,
        Capability.Owasp.READ,
        Capability.Owasp.CREATE,
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
        Capability.Playground.USE,
      ],
      [CapabilityLevel.MANAGE]: [
        Capability.TestSet.READ,
        Capability.TestSet.CREATE,
        Capability.TestSet.UPDATE,
        Capability.TestSet.DELETE,
        Capability.TestSet.GENERATE,
        Capability.TestSet.EXECUTE,
        Capability.TestSet.EXPORT,
        Capability.Test.READ,
        Capability.Test.CREATE,
        Capability.Test.UPDATE,
        Capability.Test.DELETE,
        Capability.Garak.READ,
        Capability.Garak.CREATE,
        Capability.Owasp.READ,
        Capability.Owasp.CREATE,
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
        Capability.Playground.USE,
      ],
    },
  },
  {
    id: 'observability',
    label: 'Observability',
    description: 'Traces, explorer sessions',
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
    id: 'infrastructure',
    label: 'Infrastructure',
    description: 'Models, metrics, knowledge, tools, files',
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.Model.READ,
        Capability.Metric.READ,
        Capability.Source.READ,
        Capability.Requirement.READ,
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
        Capability.Requirement.READ,
        Capability.Requirement.CREATE,
        Capability.Requirement.UPDATE,
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
        Capability.Requirement.READ,
        Capability.Requirement.CREATE,
        Capability.Requirement.UPDATE,
        Capability.Requirement.DELETE,
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
    id: 'administration',
    label: 'Administration',
    description: 'Members, projects, roles, tokens',
    levels: {
      [CapabilityLevel.NONE]: [],
      [CapabilityLevel.VIEW]: [
        Capability.Organization.READ,
        Capability.Member.READ,
        Capability.Project.READ,
        Capability.ProjectMember.READ,
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
        Capability.Polyphemus.REQUEST,
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
        Capability.Polyphemus.REQUEST,
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
// Resource names and order
// ---------------------------------------------------------------------------

export const RESOURCE_DISPLAY_NAMES: Record<string, string> = {
  test_set: 'Test Set',
  test: 'Test',
  test_configuration: 'Test Configuration',
  test_run: 'Test Run',
  test_result: 'Test Result',
  experiment: 'Experiment',
  endpoint: 'Endpoint',
  playground: 'Playground',
  comment: 'Comment',
  task: 'Task',
  preflight: 'Preflight',
  telemetry: 'Traces',
  explorer: 'Explorer',
  model: 'Model',
  metric: 'Metric',
  source: 'Knowledge Source',
  requirement: 'Requirement',
  tool: 'Tool',
  architect: 'Architect',
  file: 'File',
  organization: 'Organization',
  member: 'Member',
  project: 'Project',
  project_member: 'Project Member',
  role: 'Role',
  token: 'API Token',
  recycle: 'Recycle Bin',
  sso: 'SSO',
  api_clients: 'API Client',
  polyphemus: 'Polyphemus',
  annotation: 'Annotation',
  insights: 'Insights',
  job: 'Job',
  notification: 'Notification',
  usage: 'Usage',
  // Named only by the audit log: sign-ins, passwords, the log itself.
  audit_log: 'Audit Log',
  audit_destination: 'Streaming Destination',
  session: 'Session',
  password: 'Password',
};

export const RESOURCE_ORDER_BY_AREA: Record<string, readonly string[]> = {
  'test-resources': [
    'test_set',
    'test',
    'test_configuration',
    'test_run',
    'test_result',
    'experiment',
    'endpoint',
    'comment',
    'task',
    'preflight',
  ],
  observability: ['telemetry', 'explorer'],
  infrastructure: [
    'model',
    'metric',
    'source',
    'requirement',
    'tool',
    'architect',
    'file',
  ],
  administration: [
    'organization',
    'member',
    'project',
    'project_member',
    'role',
    'token',
    'recycle',
    'sso',
    'api_clients',
    'polyphemus',
    // No role-editor capability yet; listed so the audit log files them here.
    'audit_log',
    'audit_destination',
    'session',
    'password',
  ],
};

/** A resource's on-screen name. One with no entry reads as words: `foo_bar` is "Foo bar". */
export function resourceDisplayName(resource: string): string {
  const name = RESOURCE_DISPLAY_NAMES[resource];
  if (name) return name;
  const words = resource.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The resources an area covers: its listed order, then any other resource its capabilities name. */
export function resourcesInArea(area: ResourceArea): readonly string[] {
  const listed = RESOURCE_ORDER_BY_AREA[area.id] ?? [];
  const fromCaps = Object.values(area.levels)
    .flat()
    .map(cap => cap.split(':')[0]);
  return [...new Set([...listed, ...fromCaps])];
}

/** The area a resource belongs to, or undefined for one no area covers. */
export function areaForResource(resource: string): ResourceArea | undefined {
  return RESOURCE_AREAS.find(area => resourcesInArea(area).includes(resource));
}
