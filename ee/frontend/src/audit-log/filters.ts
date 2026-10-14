/** The filter drawer's state. Search and the category chips live on the toolbar. */
export interface AuditEventFilters {
  /** A full action name, e.g. `endpoint.updated`; '' means any. */
  action: string;
  /** The actor's user id; '' means anyone. */
  actor: string;
  outcome: string;
  channel: string;
  /** `yyyy-mm-dd`, in the viewer's time zone. */
  from: string;
  to: string;
}

export const EMPTY_AUDIT_EVENT_FILTERS: AuditEventFilters = {
  action: '',
  actor: '',
  outcome: '',
  channel: '',
  from: '',
  to: '',
};

export function countActiveAuditEventFilters(f: AuditEventFilters): number {
  return Object.values(f).filter(value => value !== '').length;
}

export const auditLogQueryKeys = {
  all: ['audit-log'] as const,
  actions: () => [...auditLogQueryKeys.all, 'actions'] as const,
  event: (id: string) => [...auditLogQueryKeys.all, 'event', id] as const,
  related: (traceId: string) =>
    [...auditLogQueryKeys.all, 'related', traceId] as const,
  settings: () => [...auditLogQueryKeys.all, 'settings'] as const,
  roles: () => [...auditLogQueryKeys.all, 'roles'] as const,
  members: () => [...auditLogQueryKeys.all, 'members'] as const,
  allExports: () => [...auditLogQueryKeys.all, 'exports'] as const,
  exports: (userId: string) =>
    [...auditLogQueryKeys.allExports(), userId] as const,
};
