import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  PaginationParams,
  PaginatedResponse,
} from '@/utils/api-client/interfaces/pagination';

/**
 * A list page's filter/sort/fetch behavior, declared once.
 *
 * What every list page repeats -- the per-entity OData `$filter` builder,
 * the API list params, and the active-filter count -- is derived from this
 * object by `src/utils/list/{odata,params}.ts`.
 */

// ── Filter specs ──────────────────────────────────────────────────────────────

/** Case-insensitive `contains` across several columns, OR'd together. */
export interface SearchFilterSpec {
  kind: 'search';
  columns: readonly string[];
  /** Extend the search into a to-many navigation, e.g. tag names or linked metric names. */
  navs?: readonly { nav: string; columns: readonly string[] }[];
}

/** Single-value pill: `tolower(column) eq tolower(value)`. */
export interface EnumFilterSpec {
  kind: 'enum';
  column: string;
  /** Compare exactly instead of wrapping both sides in `tolower()`. */
  caseSensitive?: boolean;
}

/** Multi-select pill: the values OR'd over one column. */
export interface MultiEnumFilterSpec {
  kind: 'multiEnum';
  column: string;
  caseSensitive?: boolean;
}

/** Tri-state boolean: `''` (no filter), `'true'`, or `'false'`. */
export interface BoolFilterSpec {
  kind: 'bool';
  column: string;
}

/** Many-to-many navigation filter: `nav/any(x: tolower(x/col) eq tolower(v))`. */
export interface NavAnyFilterSpec {
  kind: 'navAny';
  /** Navigation property, e.g. `_tags_relationship`. */
  nav: string;
  /** Column path under the `x` alias, e.g. `x/tag/name`. */
  column: string;
  /** Set when the filter carries a list of values rather than one. */
  multi?: boolean;
}

/**
 * Escape hatch for a filter OData can't express generically -- JSONB
 * containment, a pseudo-value that maps to a different column, a field with no
 * backend column at all. Return `undefined` to contribute no clause.
 *
 * `multi` marks the filter value as a list rather than a single string.
 */
export interface RawFilterSpec {
  kind: 'raw';
  multi?: boolean;
  toOData?: (value: string & string[]) => string | undefined;
}

export type FilterSpec =
  | SearchFilterSpec
  | EnumFilterSpec
  | MultiEnumFilterSpec
  | BoolFilterSpec
  | NavAnyFilterSpec
  | RawFilterSpec;

export type FilterSpecMap = Record<string, FilterSpec>;

/** `multiEnum`, multi `navAny` and multi `raw` carry `string[]`; everything else `string`. */
type ValueOf<F extends FilterSpec> = F extends { kind: 'multiEnum' }
  ? string[]
  : F extends { kind: 'navAny' | 'raw'; multi: true }
    ? string[]
    : string;

/**
 * The per-entity filters object, derived from the spec map. `-readonly` strips
 * the modifier a `as const` descriptor would otherwise propagate onto values.
 */
export type FiltersOf<S extends FilterSpecMap> = {
  -readonly [K in keyof S]: ValueOf<S[K]>;
};

// ── Descriptor ────────────────────────────────────────────────────────────────

export interface ListSort {
  by: string;
  order: 'asc' | 'desc';
}

/** A list page's page/sort/filter state, as held by client-side state. */
export interface ListState<S extends FilterSpecMap> {
  /** 1-indexed. */
  page: number;
  pageSize: number;
  sort: ListSort;
  filters: FiltersOf<S>;
}

export type ListParams = PaginationParams & Record<string, unknown>;

/**
 * How rows of this list are deleted. Declaring it on the descriptor gives the
 * grid its trailing delete action, the confirm modal, and (when `bulk` is set)
 * the checkbox-selection bulk-delete mode — no per-grid wiring.
 */
export interface ListDeleteSpec<TResp = unknown> {
  /** Calls the entity's `DELETE .../bulk` endpoint. Enables checkbox bulk mode. */
  bulk?: (factory: ApiClientFactory, ids: string[]) => Promise<TResp>;
  /** Single-row delete, for entities without a bulk endpoint. */
  one?: (factory: ApiClientFactory, id: string) => Promise<unknown>;
  /** e.g. `Capability.TestRun.DELETE`. */
  capability: string;
  /**
   * `'row'`: the response rows carry `permitted_actions` — gate per row via
   * `can(row, capability)` (also gates row selectability). `'ambient'`: gate
   * once via `useCan(capability)`.
   */
  capabilityMode: 'row' | 'ambient';
  labelSingular: string;
  labelPlural: string;
  // Method syntax on purpose: bivariant params keep a descriptor with a
  // concrete TResp assignable to the `ListDescriptor<T, S>` (TDeleteResp =
  // unknown) signatures the hooks use.
  /** Owner-only delete rule: count of ids skipped by the bulk response. */
  getSkippedCount?(response: TResp): number;
  /** Reason shown alongside the skipped count, e.g. "not yours to delete". */
  skippedReason?: string;
  /**
   * Tooltip on the disabled checkbox of a row the caller can't delete, when
   * `capabilityMode` is `'row'`. Defaults to "Only the owner can delete this
   * <labelSingular>".
   */
  notSelectableReason?: string;
  /** Confirm-modal body override; `count` is 1 for a single-row delete. */
  confirmMessage?: (count: number) => string;
}

export interface ListDescriptor<
  T,
  S extends FilterSpecMap,
  TDeleteResp = unknown,
> {
  title: string;
  description?: string;
  /** Noun used in the `AccessDenied` message, e.g. `endpoints`. */
  resource: string;
  /** A single capability, or two OR'd together. */
  capability: string | readonly [string, string];
  defaultPageSize: number;
  defaultSort: ListSort;
  filters: S;
  list: (
    factory: ApiClientFactory,
    params: ListParams
  ) => Promise<PaginatedResponse<T>>;
  /**
   * Query params derived from filters that aren't OData -- Test Runs'
   * `has_experiment`/`has_reviews` are top-level params, not `$filter` clauses.
   */
  extraParams?: (filters: FiltersOf<S>) => Record<string, unknown>;
  delete?: ListDeleteSpec<TDeleteResp>;
}

type DescriptorInput<T, S extends FilterSpecMap, TDeleteResp> = Omit<
  ListDescriptor<T, S, TDeleteResp>,
  'defaultSort'
> & {
  defaultSort?: ListSort;
};

/** Every list endpoint sorts newest-first unless the descriptor says otherwise. */
const DEFAULT_SORT: ListSort = { by: 'created_at', order: 'desc' };

export function defineList<
  T,
  const S extends FilterSpecMap,
  TDeleteResp = unknown,
>(
  descriptor: DescriptorInput<T, S, TDeleteResp>
): ListDescriptor<T, S, TDeleteResp> {
  return { defaultSort: DEFAULT_SORT, ...descriptor };
}

/** The empty value for a spec -- `[]` for the list kinds, `''` for the rest. */
export function emptyFilterValue(spec: FilterSpec): string | string[] {
  return isMultiValued(spec) ? [] : '';
}

export function isMultiValued(spec: FilterSpec): boolean {
  if (spec.kind === 'multiEnum') return true;
  if (spec.kind === 'navAny' || spec.kind === 'raw') return spec.multi === true;
  return false;
}

/** All filters cleared -- the baseline a filter drawer resets to. */
export function emptyFilters<S extends FilterSpecMap>(
  descriptor: ListDescriptor<unknown, S>
): FiltersOf<S> {
  const out: Record<string, string | string[]> = {};
  for (const [key, spec] of Object.entries(descriptor.filters)) {
    out[key] = emptyFilterValue(spec);
  }
  return out as FiltersOf<S>;
}
