/**
 * How audit events read on screen.
 *
 * Action labels are derived, not listed: the resource's name from the shared
 * catalog plus the past verb, so `endpoint.updated` reads "Endpoint updated"
 * (plan section 3). The only hand-written labels are for the audit-only
 * sign-in actions, which no capability describes.
 */

import {
  areaForResource,
  resourceDisplayName,
  type ResourceArea,
} from '../shared/resource-catalog';
import {
  AuditActorType,
  AuditChannel,
  AuditOutcome,
  type AuditEvent,
} from './types';

export const CHANNEL_LABELS: Record<AuditChannel, string> = {
  [AuditChannel.WEB]: 'Web app',
  [AuditChannel.SDK]: 'SDK',
  [AuditChannel.MCP]: 'MCP',
  [AuditChannel.ARCHITECT]: 'Architect',
  [AuditChannel.API]: 'API',
  [AuditChannel.JOB]: 'Job',
};

export const OUTCOME_LABELS: Record<AuditOutcome, string> = {
  [AuditOutcome.SUCCESS]: 'Success',
  [AuditOutcome.FAILURE]: 'Failed',
  [AuditOutcome.DENIED]: 'Denied',
};

export const ACTOR_TYPE_LABELS: Record<AuditActorType, string> = {
  [AuditActorType.USER]: 'User',
  [AuditActorType.API_TOKEN]: 'API token',
  [AuditActorType.API_CLIENT]: 'API client',
  [AuditActorType.SYSTEM]: 'System',
  [AuditActorType.ANONYMOUS]: 'Unauthenticated',
};

/**
 * Past verb back to its base, for "Endpoint update denied". Inverse of
 * `PAST_TENSE` in the backend's `events/audit_actions.py`; a verb missing here
 * falls back to "<label> (denied)".
 */
const BASE_VERBS: Record<string, string> = {
  cancelled: 'cancel',
  created: 'create',
  deleted: 'delete',
  executed: 'execute',
  exported: 'export',
  generated: 'generate',
  imported: 'import',
  purged: 'purge',
  reacted: 'react',
  requested: 'request',
  restored: 'restore',
  updated: 'update',
  used: 'use',
  viewed: 'view',
};

/** Audit-only actions whose derived label would read wrong ("Session signed in"). */
const AUDIT_ONLY_LABELS: Record<
  string,
  Partial<Record<AuditOutcome, string>>
> = {
  'session.signed_in': {
    [AuditOutcome.SUCCESS]: 'Signed in',
    [AuditOutcome.FAILURE]: 'Sign-in failed',
  },
  'session.refreshed': {
    [AuditOutcome.SUCCESS]: 'Session refreshed',
    [AuditOutcome.FAILURE]: 'Session refresh failed',
  },
  'session.signed_out': { [AuditOutcome.SUCCESS]: 'Signed out' },
  'token.exchanged': {
    [AuditOutcome.SUCCESS]: 'Token exchanged',
    [AuditOutcome.FAILURE]: 'Token exchange failed',
  },
};

const OUTCOME_SUFFIX: Record<Exclude<AuditOutcome, 'success'>, string> = {
  [AuditOutcome.FAILURE]: 'failed',
  [AuditOutcome.DENIED]: 'denied',
};

export function splitAction(action: string): {
  resource: string;
  verb: string;
} {
  const dot = action.indexOf('.');
  if (dot < 0) return { resource: action, verb: '' };
  return { resource: action.slice(0, dot), verb: action.slice(dot + 1) };
}

function isOutcome(value: string): value is AuditOutcome {
  return Object.values(AuditOutcome).includes(value as AuditOutcome);
}

/**
 * "Endpoint updated" for a success; "Endpoint update denied" or "Endpoint
 * update failed" otherwise.
 */
export function actionLabel(
  action: string,
  outcome: string = AuditOutcome.SUCCESS
): string {
  const result = isOutcome(outcome) ? outcome : AuditOutcome.SUCCESS;
  const special = AUDIT_ONLY_LABELS[action]?.[result];
  if (special) return special;

  const { resource, verb } = splitAction(action);
  const name = resourceDisplayName(resource);
  const words = verb.replace(/_/g, ' ');
  if (result === AuditOutcome.SUCCESS) return `${name} ${words}`.trim();

  const suffix = OUTCOME_SUFFIX[result];
  const base = BASE_VERBS[verb];
  return base ? `${name} ${base} ${suffix}` : `${name} ${words} (${suffix})`;
}

/** The role editor's area for an action's resource, for its category chip. */
export function actionArea(action: string): ResourceArea | undefined {
  return areaForResource(splitAction(action).resource);
}

export function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel as AuditChannel] ?? channel;
}

export function outcomeLabel(outcome: string): string {
  return OUTCOME_LABELS[outcome as AuditOutcome] ?? outcome;
}

export function actorTypeLabel(actorType: string): string {
  return ACTOR_TYPE_LABELS[actorType as AuditActorType] ?? actorType;
}

/**
 * The actor's name and a second line. `actor_label` is snapshotted as
 * "Name <email>" (or the email alone) when the event was written.
 */
export function actorDisplay(event: AuditEvent): {
  name: string;
  detail: string | null;
} {
  const label = event.actor_label?.trim();
  const typeLabel = actorTypeLabel(event.actor_type);
  const credential =
    event.actor_type === AuditActorType.API_TOKEN ||
    event.actor_type === AuditActorType.API_CLIENT
      ? [typeLabel, event.actor_credential_hint].filter(Boolean).join(' ')
      : null;

  if (!label) {
    return { name: typeLabel, detail: credential };
  }
  const match = label.match(/^(.*)\s<([^>]+)>$/);
  const name = match ? match[1] : label;
  const email = match ? match[2] : null;
  return { name, detail: credential ?? email };
}

/**
 * Frontend routes for a resource type, where one exists. A deleted resource has
 * no page to open.
 */
const RESOURCE_ROUTES: Record<string, string> = {
  endpoint: '/endpoints',
  experiment: '/experiments',
  metric: '/metrics',
  project: '/projects',
  requirement: '/requirements',
  source: '/knowledge',
  task: '/tasks',
  test: '/tests',
  test_run: '/test-runs',
  test_set: '/test-sets',
};

const DELETED_VERB = 'deleted';

export function resourceUrl(event: AuditEvent): string | null {
  if (!event.resource_id) return null;
  const { resource, verb } = splitAction(event.action);
  if (verb === DELETED_VERB) return null;
  const base = RESOURCE_ROUTES[resource];
  return base ? `${base}/${event.resource_id}` : null;
}

export function jobUrl(jobId: string): string {
  return `/jobs/${jobId}`;
}
