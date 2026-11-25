import type { RoleRead } from '../../../rbac/types';
import type { RoleMapping } from '../../types';
import {
  orgRoleOptions,
  parseJsonText,
  projectRoleOptions,
  toJsonText,
  type Catalog,
} from '../mapping-json';

const role = (
  name: string,
  level: number,
  extra: Partial<RoleRead> = {}
): RoleRead => ({
  id: `id-${name}`,
  name,
  display_name: name,
  description: '',
  scope: 'organization',
  level,
  is_built_in: true,
  organization_id: null,
  permissions: [],
  member_count: 0,
  ...extra,
});

const ROLES = [
  role('Owner', 100),
  role('Admin', 80),
  role('Auditor', 70),
  role('Member', 60),
  role('QA Lead', 50, { is_built_in: false, organization_id: 'org' }),
  role('Reviewer', 45, { is_built_in: false, scope: 'project' }),
  role('Viewer', 40),
  role('None', 0),
];

const CATALOG: Catalog = {
  roles: ROLES,
  projects: [
    { id: 'p-support', name: 'Support Bot' },
    { id: 'p-claims', name: 'Claims Assistant' },
    { id: 'p-dup1', name: 'Twin' },
    { id: 'p-dup2', name: 'Twin' },
  ],
};

const MAPPING: RoleMapping = {
  enabled: true,
  claim: 'groups',
  apply: 'every_sign_in',
  everyone_else: 'Viewer',
  rules: [
    { group: 'eval-admins', role_id: 'id-Admin', projects: [] },
    {
      group: 'qa-team',
      role_id: 'id-Member',
      projects: [{ project_id: 'p-support', role_id: 'id-Admin' }],
    },
    {
      group: 'claims',
      role_id: null,
      projects: [{ project_id: 'p-dup1', role_id: 'id-Reviewer' }],
    },
  ],
};

const parse = (text: string, seen: string[] = []) =>
  parseJsonText(text, true, CATALOG, seen);
const doc = (rules: unknown[], extra: Record<string, unknown> = {}) =>
  JSON.stringify({ claim: 'groups', apply: 'every_sign_in', rules, ...extra });

describe('role options', () => {
  it('never offers Owner, and offers only org-scoped roles org-wide', () => {
    const names = orgRoleOptions(ROLES).map(r => r.name);
    expect(names).not.toContain('Owner');
    expect(names).not.toContain('Reviewer');
    expect(names).toEqual([
      'Admin',
      'Auditor',
      'Member',
      'QA Lead',
      'Viewer',
      'None',
    ]);
  });

  it('keeps Owner, Auditor and None out of projects', () => {
    const names = projectRoleOptions(ROLES).map(r => r.name);
    expect(names).toEqual(['Admin', 'Member', 'QA Lead', 'Reviewer', 'Viewer']);
  });
});

describe('toJsonText / parseJsonText', () => {
  it('round-trips through names', () => {
    const text = toJsonText(MAPPING, CATALOG);
    expect(text).toContain('"role": "Admin"');
    expect(text).toContain('"Support Bot": "Admin"');
    // Two projects share a name, so that one is written by id.
    expect(text).toContain('"p-dup1": "Reviewer"');
    const { mapping, problems } = parse(text);
    expect(problems).toEqual([]);
    expect(mapping).toEqual(MAPPING);
  });

  it('writes one rule per line', () => {
    const lines = toJsonText(MAPPING, CATALOG).split('\n');
    expect(lines.filter(l => l.includes('"group"'))).toHaveLength(3);
  });

  it('reports bad JSON', () => {
    const { mapping, problems } = parse('{ "rules": [ }');
    expect(mapping).toBeNull();
    expect(problems[0].where).toBe('JSON');
  });

  it.each([['[]'], ['null'], ['"x"'], ['5']])(
    'rejects %s at the top level',
    text => {
      expect(parse(text).mapping).toBeNull();
    }
  );

  it('rejects Owner, with no "did you mean"', () => {
    const { problems } = parse(doc([{ group: 'a', role: 'Owner' }]));
    expect(problems[0].message).toMatch(/Owner can/);
  });

  it('suggests a role for a typo', () => {
    const { problems } = parse(doc([{ group: 'a', role: 'Membr' }]));
    expect(problems[0].message).toMatch(/Did you mean "Member"/);
  });

  it('matches role names case-sensitively but suggests the right case', () => {
    const { mapping, problems } = parse(doc([{ group: 'a', role: 'admin' }]));
    expect(mapping).toBeNull();
    expect(problems[0].message).toMatch(/Did you mean "Admin"/);
  });

  it('rejects a project-only role org-wide', () => {
    const { problems } = parse(doc([{ group: 'a', role: 'Reviewer' }]));
    expect(problems[0].message).toMatch(/project-only/);
  });

  it.each(['Auditor', 'None', 'Owner'])('rejects %s in a project', name => {
    const { mapping } = parse(
      doc([{ group: 'a', projects: { 'Support Bot': name } }])
    );
    expect(mapping).toBeNull();
  });

  it('suggests a project for a typo', () => {
    const { problems } = parse(
      doc([{ group: 'a', projects: { 'Support Bott': 'Member' } }])
    );
    expect(problems[0].message).toMatch(/Did you mean "Support Bot"/);
  });

  it('asks for an id when a project name is ambiguous', () => {
    const { problems } = parse(
      doc([{ group: 'a', projects: { Twin: 'Member' } }])
    );
    expect(problems[0].message).toMatch(/Two projects/);
  });

  it('rejects duplicate groups and empty groups', () => {
    expect(
      parse(
        doc([
          { group: 'a', role: 'Admin' },
          { group: 'a', role: 'Viewer' },
        ])
      ).mapping
    ).toBeNull();
    expect(parse(doc([{ group: '', role: 'Admin' }])).mapping).toBeNull();
    expect(parse(doc([{ role: 'Admin' }])).mapping).toBeNull();
    expect(parse(doc([null])).mapping).toBeNull();
  });

  it('rejects a rule that grants nothing', () => {
    const { problems } = parse(doc([{ group: 'a' }]));
    expect(problems[0].message).toMatch(/needs a "role" or "projects"/);
    expect(parse(doc([{ group: 'a', role: null }])).mapping).toBeNull();
    expect(parse(doc([{ group: 'a', projects: {} }])).mapping).toBeNull();
  });

  it('rejects projects written as a list', () => {
    expect(
      parse(doc([{ group: 'a', projects: ['Support Bot'] }])).mapping
    ).toBeNull();
  });

  it('warns when nobody signed in with a group, but still parses', () => {
    const { mapping, problems } = parse(
      doc([{ group: 'qa', role: 'Member' }]),
      ['QA']
    );
    expect(mapping).not.toBeNull();
    expect(problems[0]).toMatchObject({ level: 'warning' });
  });

  it('warns about leading or trailing spaces', () => {
    const { problems } = parse(doc([{ group: ' qa', role: 'Member' }]));
    expect(problems[0].message).toMatch(/space/);
  });

  it.each([
    [{ claim: '' }],
    [{ claim: [] }],
    [{ claim: ['a', ''] }],
    [{ claim: ['a', 'b', 'c', 'd', 'e'] }],
    [{ claim: 5 }],
    [{ apply: 'sometimes' }],
    [{ everyone_else: 'Owner' }],
  ])('rejects %j', extra => {
    expect(parse(doc([], extra)).mapping).toBeNull();
  });

  it('accepts nested and URL claims', () => {
    expect(
      parse(doc([], { claim: ['realm_access', 'roles'] })).mapping?.claim
    ).toEqual(['realm_access', 'roles']);
    expect(
      parse(doc([], { claim: 'https://acme.com/groups' })).mapping?.claim
    ).toBe('https://acme.com/groups');
  });

  it('defaults missing settings', () => {
    const { mapping } = parse('{ "rules": [] }');
    expect(mapping).toMatchObject({
      claim: 'groups',
      apply: 'every_sign_in',
      everyone_else: 'keep',
    });
  });

  it('warns about unknown top-level keys', () => {
    const { mapping, problems } = parse(doc([], { strict: true }));
    expect(mapping).not.toBeNull();
    expect(problems[0]).toMatchObject({ level: 'warning', where: 'strict' });
  });

  it('caps the number of rules', () => {
    const many = Array.from({ length: 201 }, (_, i) => ({
      group: `g${i}`,
      role: 'Viewer',
    }));
    expect(parse(doc(many)).mapping).toBeNull();
  });

  it('puts errors before warnings', () => {
    const { problems } = parse(
      doc([
        { group: ' a', role: 'Admin' },
        { group: 'b', role: 'Nope' },
      ])
    );
    expect(problems.map(p => p.level)).toEqual(['error', 'warning']);
  });
});
