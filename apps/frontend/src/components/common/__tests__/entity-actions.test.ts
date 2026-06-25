import { resolveEntityActions, type EntityAction } from '../entity-actions';

interface Thing {
  permitted_actions?: string[];
  resolved?: boolean;
}

const actions: EntityAction<Thing>[] = [
  { id: 'edit', label: 'Edit', capability: 'thing:update', onSelect: () => {} },
  {
    id: 'delete',
    label: 'Delete',
    capability: 'thing:delete',
    isEnabled: t => !t.resolved,
    disabledReason: 'Resolved items cannot be deleted',
    onSelect: () => {},
  },
  { id: 'share', label: 'Share', onSelect: () => {} }, // no capability — always permitted
  {
    id: 'taskify',
    label: 'Taskify',
    isVisible: () => false, // non-permission visibility
    onSelect: () => {},
  },
];

const ids = (subject: Thing | null | undefined) =>
  resolveEntityActions(subject, actions).map(r => r.action.id);

describe('resolveEntityActions', () => {
  it('returns nothing for a null subject (fail-closed)', () => {
    expect(resolveEntityActions(null, actions)).toEqual([]);
    expect(resolveEntityActions(undefined, actions)).toEqual([]);
  });

  it('hides actions whose capability is not granted; keeps capability-less ones', () => {
    // Has update but not delete; taskify hidden by isVisible.
    expect(ids({ permitted_actions: ['thing:update'] })).toEqual([
      'edit',
      'share',
    ]);
  });

  it('shows a permitted action disabled when a business rule (isEnabled) fails', () => {
    const resolved = resolveEntityActions(
      { permitted_actions: ['thing:update', 'thing:delete'], resolved: true },
      actions
    );
    const del = resolved.find(r => r.action.id === 'delete');
    expect(del).toBeDefined();
    expect(del!.enabled).toBe(false); // shown, but disabled — not hidden
  });

  it('treats permission denial and business-rule disable differently', () => {
    // No delete permission at all → delete is absent (not a disabled entry).
    expect(ids({ permitted_actions: [] })).toEqual(['share']);
  });
});
