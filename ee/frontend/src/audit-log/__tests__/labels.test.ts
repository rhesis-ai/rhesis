/**
 * Action labels, actor names, resource links and the category filter.
 *
 * Labels are derived from the shared resource catalog plus the past verb
 * (plan section 3), so these pin the wording rather than a list.
 */

import { RESOURCE_DISPLAY_NAMES } from '../../shared/resource-catalog';
import {
  actionArea,
  actionLabel,
  actorDisplay,
  channelLabel,
  resourceUrl,
} from '../labels';
import { AUDIT_EVENT_FILTERS, areaClause } from '../list';
import type { AuditEvent } from '../types';

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: 'e1',
    organization_id: 'o1',
    project_id: null,
    occurred_at: '2026-10-05T12:00:00Z',
    recorded_at: '2026-10-05T12:00:00Z',
    action: 'endpoint.updated',
    outcome: 'success',
    status_code: null,
    actor_type: 'user',
    actor_id: 'u1',
    actor_credential_id: null,
    actor_credential_hint: null,
    actor_label: 'Harry Cruz <harry@example.com>',
    channel: 'web',
    ip: null,
    user_agent: null,
    resource_id: 'r1',
    resource_label: 'travel-agent-prod',
    request_id: null,
    trace_id: 't1',
    span_id: 's1',
    job_id: null,
    changes: [],
    ...overrides,
  };
}

describe('actionLabel', () => {
  it('reads a success as the resource name plus the past verb', () => {
    expect(actionLabel('endpoint.updated')).toBe('Endpoint updated');
    expect(actionLabel('test_set.exported')).toBe('Test Set exported');
    expect(actionLabel('member.updated')).toBe('Member updated');
  });

  it('uses the role editor names, so the two screens agree', () => {
    expect(actionLabel('source.created')).toBe(
      `${RESOURCE_DISPLAY_NAMES.source} created`
    );
  });

  it('reads a denial with the base verb', () => {
    expect(actionLabel('endpoint.updated', 'denied')).toBe(
      'Endpoint update denied'
    );
    expect(actionLabel('test_set.executed', 'denied')).toBe(
      'Test Set execute denied'
    );
    expect(actionLabel('test_set.viewed', 'denied')).toBe(
      'Test Set view denied'
    );
  });

  it('names the audit-only sign-in actions by hand', () => {
    expect(actionLabel('session.signed_in')).toBe('Signed in');
    expect(actionLabel('session.signed_in', 'failure')).toBe('Sign-in failed');
    expect(actionLabel('session.refreshed', 'failure')).toBe(
      'Session refresh failed'
    );
    expect(actionLabel('token.exchanged', 'failure')).toBe(
      'Token exchange failed'
    );
    expect(actionLabel('password.reset')).toBe('Password reset');
  });

  it('falls back to words for a resource the catalog does not know', () => {
    expect(actionLabel('widget_thing.created')).toBe('Widget thing created');
    expect(actionLabel('widget.frobbed', 'denied')).toBe(
      'Widget frobbed (denied)'
    );
  });
});

describe('actionArea', () => {
  it('files actions under the role editor areas', () => {
    expect(actionArea('endpoint.updated')?.label).toBe('Test Resources');
    expect(actionArea('metric.updated')?.label).toBe('Infrastructure');
    expect(actionArea('telemetry.deleted')?.label).toBe('Observability');
    expect(actionArea('session.signed_in')?.label).toBe('Administration');
    expect(actionArea('audit_log.viewed')?.label).toBe('Administration');
  });
});

describe('channelLabel', () => {
  it('covers every source the backend records', () => {
    expect(
      ['web', 'sdk', 'mcp', 'architect', 'api', 'job'].map(channelLabel)
    ).toEqual(['Web app', 'SDK', 'MCP', 'Architect', 'API', 'Job']);
  });
});

describe('actorDisplay', () => {
  it('splits the snapshotted "Name <email>" label', () => {
    expect(actorDisplay(makeEvent())).toEqual({
      name: 'Harry Cruz',
      detail: 'harry@example.com',
    });
  });

  it('shows the token hint for a token actor', () => {
    expect(
      actorDisplay(
        makeEvent({ actor_type: 'api_token', actor_credential_hint: 'rh-ab12' })
      )
    ).toEqual({ name: 'Harry Cruz', detail: 'API token rh-ab12' });
  });

  it('names an unauthenticated actor without a label', () => {
    expect(
      actorDisplay(makeEvent({ actor_type: 'anonymous', actor_label: null }))
    ).toEqual({ name: 'Unauthenticated', detail: null });
  });
});

describe('resourceUrl', () => {
  it('links a resource type that has a page', () => {
    expect(resourceUrl(makeEvent())).toBe('/endpoints/r1');
    expect(resourceUrl(makeEvent({ action: 'source.updated' }))).toBe(
      '/knowledge/r1'
    );
  });

  it('has no link for a deleted resource, an unrouted type, or no id', () => {
    expect(resourceUrl(makeEvent({ action: 'endpoint.deleted' }))).toBeNull();
    expect(resourceUrl(makeEvent({ action: 'member.updated' }))).toBeNull();
    expect(resourceUrl(makeEvent({ resource_id: null }))).toBeNull();
  });
});

describe('audit event filters', () => {
  it('turns a category into startswith clauses over its resources', () => {
    const clause = areaClause('observability');
    expect(clause).toBe(
      "(startswith(action,'telemetry.') or startswith(action,'explorer.'))"
    );
  });

  it('ignores an unknown category', () => {
    expect(areaClause('nope')).toBeUndefined();
  });

  it('bounds a date range by whole days in UTC literals', () => {
    const from = AUDIT_EVENT_FILTERS.from.toOData('2026-06-15');
    const to = AUDIT_EVENT_FILTERS.to.toOData('2026-06-15');
    const literal = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
    expect(from).toMatch(/^occurred_at ge /);
    expect(from).toMatch(literal);
    // The end day is whole: everything before the next local midnight.
    expect(to).toMatch(/^occurred_at lt /);
    const start = Date.parse(from?.split(' ').pop() ?? '');
    const end = Date.parse(to?.split(' ').pop() ?? '');
    expect(end - start).toBe(24 * 60 * 60 * 1000);
    expect(AUDIT_EVENT_FILTERS.from.toOData('')).toBeUndefined();
  });

  it('filters by actor id unquoted', () => {
    expect(AUDIT_EVENT_FILTERS.actor.toOData('u1')).toBe('actor_id eq u1');
  });
});
