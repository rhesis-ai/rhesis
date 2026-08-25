import { escapeODataValue } from '@/utils/odata-filter';
import type {
  DirectoryDescriptor,
  FilterSpec,
  FilterSpecMap,
  FiltersOf,
} from './define';

/** `tolower(col) eq tolower('v')`, or an exact compare when case matters. */
function eq(column: string, value: string, caseSensitive?: boolean): string {
  const v = escapeODataValue(value);
  return caseSensitive
    ? `${column} eq '${v}'`
    : `tolower(${column}) eq tolower('${v}')`;
}

/** Wraps OR'd clauses in parentheses so they can't bind loosely against `and`. */
function anyOf(clauses: string[]): string | undefined {
  if (clauses.length === 0) return undefined;
  if (clauses.length === 1) return clauses[0];
  return `(${clauses.join(' or ')})`;
}

function containsClause(column: string, q: string): string {
  return `contains(tolower(${column}),tolower('${q}'))`;
}

function clauseFor(
  spec: FilterSpec,
  value: string | string[]
): string | undefined {
  switch (spec.kind) {
    case 'search': {
      const term = typeof value === 'string' ? value.trim() : '';
      if (!term) return undefined;
      const q = escapeODataValue(term);
      const clauses = spec.columns.map(c => containsClause(c, q));
      for (const navSpec of spec.navs ?? []) {
        const inner = anyOf(
          navSpec.columns.map(c => containsClause(`x/${c}`, q))
        );
        if (inner) clauses.push(`${navSpec.nav}/any(x: ${inner})`);
      }
      return anyOf(clauses);
    }

    case 'enum': {
      if (typeof value !== 'string' || !value) return undefined;
      return eq(spec.column, value, spec.caseSensitive);
    }

    case 'multiEnum': {
      const values = Array.isArray(value) ? value.filter(Boolean) : [];
      return anyOf(values.map(v => eq(spec.column, v, spec.caseSensitive)));
    }

    case 'bool': {
      if (value !== 'true' && value !== 'false') return undefined;
      return `${spec.column} eq ${value}`;
    }

    case 'navAny': {
      const values = Array.isArray(value)
        ? value.filter(Boolean)
        : value
          ? [value]
          : [];
      // The `x` alias is fixed; `spec.column` is written against it.
      const inner = anyOf(values.map(v => eq(spec.column, v)));
      return inner ? `${spec.nav}/any(x: ${inner})` : undefined;
    }

    case 'raw':
      return spec.toOData?.(value as string & string[]);
  }
}

/**
 * Builds the `$filter` for a directory page from its descriptor. Replaces the
 * per-entity `build<Entity>ODataFilter` functions -- clauses are AND'd, and an
 * inactive filter contributes nothing. Returns undefined when nothing is active,
 * so the caller can omit `$filter` entirely.
 *
 * `extra` is for clauses the filters don't own, e.g. scoping an embedded grid to
 * one project.
 */
export function buildDirectoryFilter<S extends FilterSpecMap>(
  descriptor: DirectoryDescriptor<unknown, S>,
  filters: FiltersOf<S>,
  extra: (string | undefined)[] = []
): string | undefined {
  const parts = [...extra];

  for (const [key, spec] of Object.entries(descriptor.filters)) {
    const clause = clauseFor(
      spec,
      (filters as Record<string, string | string[]>)[key]
    );
    if (clause) parts.push(clause);
  }

  const active = parts.filter(Boolean) as string[];
  if (active.length === 0) return undefined;
  return active.length === 1 ? active[0] : active.join(' and ');
}
