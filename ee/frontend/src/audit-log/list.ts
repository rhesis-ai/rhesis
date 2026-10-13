import { Capability } from '@/constants/capabilities';
import { defineList, type FiltersOf } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';
import { RESOURCE_AREAS, resourcesInArea } from '../shared/resource-catalog';
import {
  AUDIT_EVENTS_SORT_FIELD,
  AuditLogClient,
} from './api/audit-log-client';
import type { AuditEvent } from './types';

/** Local midnight starting a `yyyy-mm-dd` day, `offset` days later, as a UTC OData literal. */
function localDayStart(day: string, offset = 0): string | undefined {
  const date = new Date(`${day}T00:00:00`);
  if (Number.isNaN(date.getTime())) return undefined;
  date.setDate(date.getDate() + offset);
  // Whole seconds: the literal needs no fraction.
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/** Every action whose resource sits in the area, OR'd. */
export function areaClause(areaId: string): string | undefined {
  const area = RESOURCE_AREAS.find(a => a.id === areaId);
  if (!area) return undefined;
  const clauses = resourcesInArea(area).map(
    resource => `startswith(action,'${escapeODataValue(resource)}.')`
  );
  if (clauses.length === 0) return undefined;
  return clauses.length === 1 ? clauses[0] : `(${clauses.join(' or ')})`;
}

export const AUDIT_EVENT_FILTERS = {
  search: {
    kind: 'search',
    columns: ['actor_label', 'resource_label', 'action'],
  },
  /** A role editor area id; the category chips. */
  area: {
    kind: 'raw',
    toOData: (value: string) => (value ? areaClause(value) : undefined),
  },
  action: { kind: 'enum', column: 'action', caseSensitive: true },
  outcome: { kind: 'enum', column: 'outcome', caseSensitive: true },
  channel: { kind: 'enum', column: 'channel', caseSensitive: true },
  /** UUID compare, unquoted. */
  actor: {
    kind: 'raw',
    toOData: (value: string) =>
      value ? `actor_id eq ${escapeODataValue(value)}` : undefined,
  },
  // The whole end day is included: picking today means up to now.
  from: {
    kind: 'raw',
    toOData: (value: string) => {
      const bound = value ? localDayStart(value) : undefined;
      return bound ? `occurred_at ge ${bound}` : undefined;
    },
  },
  to: {
    kind: 'raw',
    toOData: (value: string) => {
      const bound = value ? localDayStart(value, 1) : undefined;
      return bound ? `occurred_at lt ${bound}` : undefined;
    },
  },
} as const;

export type AuditEventListFilters = FiltersOf<typeof AUDIT_EVENT_FILTERS>;

export const auditEventsList = defineList<
  AuditEvent,
  typeof AUDIT_EVENT_FILTERS
>({
  title: 'Audit Log',
  resource: 'audit log',
  capability: Capability.AuditLog.READ,
  defaultPageSize: 25,
  defaultSort: { by: AUDIT_EVENTS_SORT_FIELD, order: 'desc' },
  filters: AUDIT_EVENT_FILTERS,
  // The audit client is EE, so it is not on the core factory.
  list: (_factory, params) => new AuditLogClient().listEvents(params),
});
