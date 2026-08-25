import { defineDirectory, emptyFilters } from '../define';
import {
  countActiveFilters,
  directoryListParams,
  hasActiveFilters,
} from '../params';
import { buildDirectoryFilter } from '../odata';
import type { PaginatedResponse } from '@/utils/api-client/interfaces/pagination';

const widgets = defineDirectory({
  title: 'Widgets',
  resource: 'widgets',
  capability: 'widget:read',
  defaultPageSize: 25,
  list: async () => ({}) as PaginatedResponse<unknown>,
  filters: {
    search: {
      kind: 'search',
      columns: ['name', 'description'],
      navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
    },
    status: { kind: 'enum', column: 'status/name' },
    kind: { kind: 'enum', column: 'kind', caseSensitive: true },
    backends: { kind: 'multiEnum', column: 'backend_type' },
    archived: { kind: 'bool', column: 'is_archived' },
    tags: {
      kind: 'navAny',
      nav: '_tags_relationship',
      column: 'x/tag/name',
      multi: true,
    },
  },
} as const);

const empty = {
  page: 1,
  pageSize: 25,
  sort: widgets.defaultSort,
  filters: emptyFilters(widgets),
};

describe('emptyFilters', () => {
  it('gives every filter its empty value -- [] for list kinds, "" for the rest', () => {
    expect(empty.filters).toEqual({
      search: '',
      status: '',
      kind: '',
      backends: [],
      archived: '',
      tags: [],
    });
  });
});

describe('buildDirectoryFilter', () => {
  const filterFor = (partial: Partial<typeof empty.filters>) =>
    buildDirectoryFilter(widgets, { ...empty.filters, ...partial });

  it('contributes nothing when no filter is active', () => {
    expect(filterFor({})).toBeUndefined();
  });

  it('ORs a search across every configured column, case-insensitively', () => {
    expect(filterFor({ search: 'abc' })).toBe(
      "(contains(tolower(name),tolower('abc')) or contains(tolower(description),tolower('abc')) or _tags_relationship/any(x: contains(tolower(x/tag/name),tolower('abc'))))"
    );
  });

  it('ignores a whitespace-only search', () => {
    expect(filterFor({ search: '   ' })).toBeUndefined();
  });

  it('escapes quotes so a search term cannot break out of the clause', () => {
    expect(filterFor({ search: "o'brien" })).toContain("tolower('o''brien')");
  });

  it('lowercases both sides of an enum compare unless told not to', () => {
    expect(filterFor({ status: 'Active' })).toBe(
      "tolower(status/name) eq tolower('Active')"
    );
    expect(filterFor({ kind: 'Exact' })).toBe("kind eq 'Exact'");
  });

  it('ORs a multi-select and parenthesises it', () => {
    expect(filterFor({ backends: ['a', 'b'] })).toBe(
      "(tolower(backend_type) eq tolower('a') or tolower(backend_type) eq tolower('b'))"
    );
  });

  it('emits a bare boolean, and only for a real true/false', () => {
    expect(filterFor({ archived: 'true' })).toBe('is_archived eq true');
    expect(filterFor({ archived: '' })).toBeUndefined();
  });

  it('wraps navigation filters in any()', () => {
    expect(filterFor({ tags: ['red'] })).toBe(
      "_tags_relationship/any(x: tolower(x/tag/name) eq tolower('red'))"
    );
  });

  it('ANDs active filters together', () => {
    expect(filterFor({ status: 'Active', archived: 'false' })).toBe(
      "tolower(status/name) eq tolower('Active') and is_archived eq false"
    );
  });

  it('accepts extra clauses the caller does not own, e.g. project scoping', () => {
    expect(
      buildDirectoryFilter(widgets, empty.filters, ["project_id eq 'p1'"])
    ).toBe("project_id eq 'p1'");
  });
});

describe('countActiveFilters', () => {
  it('does not count search -- the toolbar shows that separately from the drawer badge', () => {
    const filters = { ...empty.filters, search: 'foo' };
    expect(countActiveFilters(widgets, filters)).toBe(0);
    expect(hasActiveFilters(widgets, filters)).toBe(false);
  });

  it('counts each active drawer filter once, list or scalar', () => {
    const filters = {
      ...empty.filters,
      status: 'Active',
      backends: ['a', 'b'],
    };
    expect(countActiveFilters(widgets, filters)).toBe(2);
  });

  it('treats an empty list as inactive', () => {
    expect(
      countActiveFilters(widgets, { ...empty.filters, backends: [] })
    ).toBe(0);
  });
});

describe('directoryListParams', () => {
  it('turns a 1-indexed page into skip/limit', () => {
    const params = directoryListParams(widgets, { ...empty, page: 3 });
    expect(params.skip).toBe(50);
    expect(params.limit).toBe(25);
  });

  it('omits $filter entirely when nothing is active', () => {
    expect(directoryListParams(widgets, empty)).not.toHaveProperty('$filter');
  });

  it('maps grid-only sort fields onto their API names', () => {
    const params = directoryListParams(widgets, {
      ...empty,
      sort: { by: 'tags', order: 'asc' },
    });
    expect(params.sort_by).toBe('tags_count');
    expect(params.sort_order).toBe('asc');
  });
});
