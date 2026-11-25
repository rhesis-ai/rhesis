/**
 * The "Edit as JSON" view of a role mapping.
 *
 * The API stores role and project ids so renames don't break rules; people
 * read and write names. This module converts both ways and reports problems
 * with the same rules the backend enforces on save.
 */

import type { RoleRead } from '../../rbac/types';
import type {
  ApplyMode,
  ClaimPath,
  EveryoneElse,
  MappingRule,
  RoleMapping,
} from '../types';

export interface ProjectRef {
  id: string;
  name: string;
}

export interface Catalog {
  roles: RoleRead[];
  projects: ProjectRef[];
}

export interface Problem {
  level: 'error' | 'warning';
  where: string;
  message: string;
}

export const MAX_RULES = 200;
const MAX_GROUP_LENGTH = 256;
const MAX_CLAIM_DEPTH = 4;
const APPLY_MODES: ApplyMode[] = ['every_sign_in', 'on_create'];
const FALLBACKS: EveryoneElse[] = ['keep', 'Viewer', 'None', 'block'];
const OWNER = 'Owner';
const ORG_ONLY_BUILT_IN = ['Auditor'];

export const EMPTY_ROLE_MAPPING: RoleMapping = {
  enabled: false,
  claim: 'groups',
  apply: 'every_sign_in',
  rules: [],
  everyone_else: 'keep',
};

const roleLabel = (r: RoleRead) => r.display_name || r.name;

/** Roles a rule may give org-wide: org-scoped, never Owner. */
export function orgRoleOptions(roles: RoleRead[]): RoleRead[] {
  return roles
    .filter(
      r => r.scope === 'organization' && !(r.is_built_in && r.name === OWNER)
    )
    .sort((a, b) => b.level - a.level);
}

/** Roles a rule may give in a project: not Owner, None or org-only roles. */
export function projectRoleOptions(roles: RoleRead[]): RoleRead[] {
  return roles
    .filter(
      r =>
        !(
          r.is_built_in &&
          (r.name === OWNER ||
            r.level === 0 ||
            ORG_ONLY_BUILT_IN.includes(r.name))
        )
    )
    .sort((a, b) => b.level - a.level);
}

export function roleById(
  roles: RoleRead[],
  id: string | null
): RoleRead | undefined {
  return id ? roles.find(r => r.id === id) : undefined;
}

/** A project's key in JSON: its name, or its id when two projects share the name. */
function projectKey(projects: ProjectRef[], id: string): string {
  const p = projects.find(x => x.id === id);
  if (!p) return id;
  return projects.filter(x => x.name === p.name).length > 1 ? id : p.name;
}

interface JsonRule {
  group: string;
  role?: string;
  projects?: Record<string, string>;
}

export function toJsonText(m: RoleMapping, catalog: Catalog): string {
  const rules: JsonRule[] = m.rules.map(r => {
    const out: JsonRule = { group: r.group };
    const role = roleById(catalog.roles, r.role_id);
    if (r.role_id) out.role = role ? roleLabel(role) : r.role_id;
    if (r.projects.length) {
      out.projects = Object.fromEntries(
        r.projects.map(g => {
          const pr = roleById(catalog.roles, g.role_id);
          return [
            projectKey(catalog.projects, g.project_id),
            pr ? roleLabel(pr) : g.role_id,
          ];
        })
      );
    }
    return out;
  });
  // One rule per line reads like the visual rows; the rest is plain JSON.
  const inline = (v: unknown) =>
    JSON.stringify(v)
      .replace(/([{,])"/g, '$1 "')
      .replace(/":/g, '": ')
      .replace(/}/g, ' }');
  const body = rules.length
    ? `[\n${rules.map(r => `    ${inline(r)}`).join(',\n')}\n  ]`
    : '[]';
  return [
    '{',
    `  "claim": ${JSON.stringify(m.claim)},`,
    `  "apply": ${JSON.stringify(m.apply)},`,
    `  "rules": ${body},`,
    `  "everyone_else": ${JSON.stringify(m.everyone_else)}`,
    '}',
  ].join('\n');
}

function didYouMean(word: string, options: string[]): string {
  const w = word.toLowerCase();
  const hit =
    options.find(o => o.toLowerCase() === w) ??
    options.find(o => o.toLowerCase().startsWith(w.slice(0, 3)));
  return hit ? ` Did you mean "${hit}"?` : '';
}

function findRole(roles: RoleRead[], label: string): RoleRead | undefined {
  return (
    roles.find(r => r.id === label) ??
    roles.find(r => roleLabel(r) === label) ??
    roles.find(r => r.name === label)
  );
}

function findProject(
  projects: ProjectRef[],
  key: string
): ProjectRef | 'ambiguous' | undefined {
  const byId = projects.find(p => p.id === key);
  if (byId) return byId;
  const named = projects.filter(p => p.name === key);
  if (named.length > 1) return 'ambiguous';
  return named[0];
}

function validClaim(v: unknown): v is ClaimPath {
  if (typeof v === 'string')
    return v.trim() !== '' && v.length <= MAX_GROUP_LENGTH;
  return (
    Array.isArray(v) &&
    v.length >= 1 &&
    v.length <= MAX_CLAIM_DEPTH &&
    v.every(s => typeof s === 'string' && s.trim() !== '')
  );
}

interface ParseContext {
  catalog: Catalog;
  /** Group values seen at sign-in; empty means none known yet. */
  seenGroups: string[];
  problems: Problem[];
}

function parseRoleField(
  raw: unknown,
  where: string,
  allowed: RoleRead[],
  ctx: ParseContext,
  tier: 'org' | 'project'
): string | null {
  const label = String(raw);
  if (label === OWNER) {
    ctx.problems.push({
      level: 'error',
      where,
      message: 'Owner can’t be given by a mapping.',
    });
    return null;
  }
  const role = findRole(ctx.catalog.roles, label);
  if (!role) {
    ctx.problems.push({
      level: 'error',
      where,
      message: `Unknown role "${label}".${didYouMean(label, allowed.map(roleLabel))}`,
    });
    return null;
  }
  if (!allowed.some(r => r.id === role.id)) {
    ctx.problems.push({
      level: 'error',
      where,
      message:
        tier === 'org'
          ? `${roleLabel(role)} is a project-only role.`
          : `${roleLabel(role)} can’t be given in a project.`,
    });
    return null;
  }
  return role.id;
}

function parseRule(
  raw: unknown,
  i: number,
  seen: Set<string>,
  ctx: ParseContext
): MappingRule {
  const where = `rules[${i}]`;
  const errorsBefore = ctx.problems.length;
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<
    string,
    unknown
  >;
  const group = typeof r.group === 'string' ? r.group : '';
  if (!group) {
    ctx.problems.push({ level: 'error', where, message: 'Missing "group".' });
  } else if (group.length > MAX_GROUP_LENGTH) {
    ctx.problems.push({
      level: 'error',
      where,
      message: 'Group is longer than 256 characters.',
    });
  } else if (seen.has(group)) {
    ctx.problems.push({
      level: 'error',
      where,
      message: `"${group}" has more than one rule.`,
    });
  } else if (group !== group.trim()) {
    ctx.problems.push({
      level: 'warning',
      where,
      message: `"${group}" starts or ends with a space. Groups must match exactly.`,
    });
  } else if (ctx.seenGroups.length && !ctx.seenGroups.includes(group)) {
    ctx.problems.push({
      level: 'warning',
      where,
      message: `Nobody has signed in with "${group}" yet. Check the spelling and case.`,
    });
  }
  seen.add(group);

  const role_id =
    r.role === undefined || r.role === null
      ? null
      : parseRoleField(
          r.role,
          `${where}.role`,
          orgRoleOptions(ctx.catalog.roles),
          ctx,
          'org'
        );

  const projects: MappingRule['projects'] = [];
  if (r.projects !== undefined) {
    if (
      !r.projects ||
      typeof r.projects !== 'object' ||
      Array.isArray(r.projects)
    ) {
      ctx.problems.push({
        level: 'error',
        where: `${where}.projects`,
        message: 'Use { "Project name": "Role" }.',
      });
    } else {
      for (const [key, prole] of Object.entries(
        r.projects as Record<string, unknown>
      )) {
        const pwhere = `${where}.projects`;
        const project = findProject(ctx.catalog.projects, key);
        if (project === 'ambiguous') {
          ctx.problems.push({
            level: 'error',
            where: pwhere,
            message: `Two projects are called "${key}". Use the project id instead.`,
          });
          continue;
        }
        if (!project) {
          ctx.problems.push({
            level: 'error',
            where: pwhere,
            message: `Unknown project "${key}".${didYouMean(
              key,
              ctx.catalog.projects.map(p => p.name)
            )}`,
          });
          continue;
        }
        const roleId = parseRoleField(
          prole,
          pwhere,
          projectRoleOptions(ctx.catalog.roles),
          ctx,
          'project'
        );
        if (roleId) projects.push({ project_id: project.id, role_id: roleId });
      }
    }
  }
  const newErrors = ctx.problems
    .slice(errorsBefore)
    .some(p => p.level === 'error');
  if (group && role_id === null && projects.length === 0 && !newErrors) {
    ctx.problems.push({
      level: 'error',
      where,
      message: `"${group}" needs a "role" or "projects".`,
    });
  }
  return { group, role_id, projects };
}

/** Parse the editor text. ``mapping`` is null while there are errors. */
export function parseJsonText(
  text: string,
  enabled: boolean,
  catalog: Catalog,
  seenGroups: string[] = []
): { mapping: RoleMapping | null; problems: Problem[] } {
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch (e) {
    return {
      mapping: null,
      problems: [
        {
          level: 'error',
          where: 'JSON',
          message: e instanceof Error ? e.message : 'Invalid JSON',
        },
      ],
    };
  }
  const problems: Problem[] = [];
  if (!doc || typeof doc !== 'object' || Array.isArray(doc)) {
    return {
      mapping: null,
      problems: [
        { level: 'error', where: 'JSON', message: 'Must be an object.' },
      ],
    };
  }
  const d = doc as Record<string, unknown>;
  const ctx: ParseContext = { catalog, seenGroups, problems };

  if (!Array.isArray(d.rules))
    problems.push({
      level: 'error',
      where: 'rules',
      message: 'Must be a list of rules.',
    });
  else if (d.rules.length > MAX_RULES)
    problems.push({
      level: 'error',
      where: 'rules',
      message: `At most ${MAX_RULES} rules.`,
    });
  const apply = (d.apply ?? 'every_sign_in') as ApplyMode;
  if (!APPLY_MODES.includes(apply))
    problems.push({
      level: 'error',
      where: 'apply',
      message: 'Use "every_sign_in" or "on_create".',
    });
  const everyoneElse = (d.everyone_else ?? 'keep') as EveryoneElse;
  if (!FALLBACKS.includes(everyoneElse))
    problems.push({
      level: 'error',
      where: 'everyone_else',
      message: 'Use "keep", "Viewer", "None" or "block".',
    });
  const claim = d.claim ?? 'groups';
  if (!validClaim(claim))
    problems.push({
      level: 'error',
      where: 'claim',
      message:
        'Use a claim name, or a list of up to 4 names for a nested claim.',
    });
  const known = new Set([
    'claim',
    'apply',
    'rules',
    'everyone_else',
    'enabled',
  ]);
  for (const key of Object.keys(d)) {
    if (!known.has(key))
      problems.push({
        level: 'warning',
        where: key,
        message: 'Not a setting. It will be ignored.',
      });
  }

  const seen = new Set<string>();
  const rules = (Array.isArray(d.rules) ? d.rules : []).map((r, i) =>
    parseRule(r, i, seen, ctx)
  );

  problems.sort((a, b) =>
    a.level === b.level ? 0 : a.level === 'error' ? -1 : 1
  );
  if (problems.some(p => p.level === 'error'))
    return { mapping: null, problems };
  return {
    mapping: {
      enabled,
      claim: claim as ClaimPath,
      apply,
      rules,
      everyone_else: everyoneElse,
    },
    problems,
  };
}

export function claimKey(c: ClaimPath): string {
  return JSON.stringify(c);
}

export function claimLabel(c: ClaimPath): string {
  return Array.isArray(c) ? c.join(' › ') : c;
}
