import { GridLogicOperator } from '@mui/x-data-grid';
import {
  createWildcardSearchFilter,
  createTaskWildcardSearchFilter,
  convertGridFilterModelToOData,
  convertTaskFilterModelToOData,
  convertQuickFilterToOData,
  combineFiltersToOData,
  convertTaskQuickFilterToOData,
  convertTestQuickFilterToOData,
  combineTestFiltersToOData,
  convertSourceQuickFilterToOData,
  combineSourceFiltersToOData,
  convertTestRunQuickFilterToOData,
  combineTestRunFiltersToOData,
  convertTestSetQuickFilterToOData,
  combineTestSetFiltersToOData,
  combineTaskFiltersToOData,
} from '../odata-filter';

describe('createTaskWildcardSearchFilter', () => {
  it('returns empty string for empty input', () => {
    expect(createTaskWildcardSearchFilter('')).toBe('');
    expect(createTaskWildcardSearchFilter('   ')).toBe('');
  });

  it('creates filter for title and description fields', () => {
    const result = createTaskWildcardSearchFilter('test');
    expect(result).toContain("contains(tolower(title), tolower('test'))");
    expect(result).toContain("contains(tolower(description), tolower('test'))");
    expect(result).toContain(' or ');
  });

  it('escapes single quotes in search term', () => {
    const result = createTaskWildcardSearchFilter("it's");
    expect(result).toContain("it''s");
  });

  it('trims whitespace from search term', () => {
    const result = createTaskWildcardSearchFilter('  hello  ');
    expect(result).toContain("tolower('hello')");
  });
});

describe('createWildcardSearchFilter', () => {
  it('returns empty string for empty input', () => {
    expect(createWildcardSearchFilter('')).toBe('');
  });

  it('creates filter for test-related fields', () => {
    const result = createWildcardSearchFilter('query');
    expect(result).toContain('behavior/name');
    expect(result).toContain('topic/name');
    expect(result).toContain('category/name');
    expect(result).toContain('prompt/content');
  });
});

describe('convertGridFilterModelToOData', () => {
  it('returns empty string for empty filter model', () => {
    expect(convertGridFilterModelToOData({ items: [] })).toBe('');
  });

  it('converts contains operator', () => {
    const result = convertGridFilterModelToOData({
      items: [{ field: 'name', operator: 'contains', value: 'test', id: 1 }],
    });
    expect(result).toBe("contains(tolower(name), tolower('test'))");
  });

  it('converts equals operator for strings', () => {
    const result = convertGridFilterModelToOData({
      items: [{ field: 'status', operator: 'equals', value: 'active', id: 1 }],
    });
    expect(result).toBe("tolower(status) eq tolower('active')");
  });

  it('converts startsWith and endsWith', () => {
    const startsWith = convertGridFilterModelToOData({
      items: [{ field: 'name', operator: 'startsWith', value: 'abc', id: 1 }],
    });
    expect(startsWith).toBe("startswith(tolower(name), tolower('abc'))");

    const endsWith = convertGridFilterModelToOData({
      items: [{ field: 'name', operator: 'endsWith', value: 'xyz', id: 1 }],
    });
    expect(endsWith).toBe("endswith(tolower(name), tolower('xyz'))");
  });

  it('converts comparison operators', () => {
    const gt = convertGridFilterModelToOData({
      items: [{ field: 'count', operator: '>', value: '5', id: 1 }],
    });
    expect(gt).toBe('count gt 5');
  });

  it('converts isEmpty and isNotEmpty', () => {
    const empty = convertGridFilterModelToOData({
      items: [{ field: 'name', operator: 'isEmpty', value: true, id: 1 }],
    });
    expect(empty).toBe("name eq null or name eq ''");

    const notEmpty = convertGridFilterModelToOData({
      items: [{ field: 'name', operator: 'isNotEmpty', value: true, id: 1 }],
    });
    expect(notEmpty).toBe("name ne null and name ne ''");
  });

  it('converts isAnyOf operator', () => {
    const result = convertGridFilterModelToOData({
      items: [
        {
          field: 'status',
          operator: 'isAnyOf',
          value: ['a', 'b'],
          id: 1,
        },
      ],
    });
    expect(result).toBe("(status eq 'a' or status eq 'b')");
  });

  it('joins multiple filters with AND by default', () => {
    const result = convertGridFilterModelToOData({
      items: [
        { field: 'name', operator: 'contains', value: 'a', id: 1 },
        { field: 'status', operator: 'equals', value: 'active', id: 2 },
      ],
    });
    expect(result).toContain(' and ');
  });

  it('joins multiple filters with OR when specified', () => {
    const result = convertGridFilterModelToOData({
      items: [
        { field: 'name', operator: 'contains', value: 'a', id: 1 },
        { field: 'status', operator: 'equals', value: 'active', id: 2 },
      ],
      logicOperator: GridLogicOperator.Or,
    });
    expect(result).toContain(' or ');
  });

  it('converts dot notation to OData path syntax', () => {
    const result = convertGridFilterModelToOData({
      items: [
        {
          field: 'behavior.name',
          operator: 'contains',
          value: 'test',
          id: 1,
        },
      ],
    });
    expect(result).toContain('behavior/name');
  });

  it('skips items with missing required fields', () => {
    const result = convertGridFilterModelToOData({
      items: [
        { field: 'name', operator: 'contains', value: '', id: 1 },
        { field: 'status', operator: 'equals', value: 'active', id: 2 },
      ],
    });
    expect(result).toBe("tolower(status) eq tolower('active')");
  });

  it('handles tags field with relationship path', () => {
    const result = convertGridFilterModelToOData({
      items: [
        { field: 'tags', operator: 'contains', value: 'important', id: 1 },
      ],
    });
    expect(result).toContain('_tags_relationship/any');
    expect(result).toContain('t/tag/name');
  });
});

describe('convertTaskFilterModelToOData', () => {
  it('maps task-specific fields to relationships', () => {
    const result = convertTaskFilterModelToOData({
      items: [{ field: 'status', operator: 'contains', value: 'Open', id: 1 }],
    });
    expect(result).toContain('status/name');
  });
});

describe('convertQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertQuickFilterToOData([], ['name'])).toBe('');
    expect(convertQuickFilterToOData(['test'], [])).toBe('');
  });

  it('creates OR conditions across search fields', () => {
    const result = convertQuickFilterToOData(['hello'], ['name', 'title']);
    expect(result).toContain("contains(tolower(name), tolower('hello'))");
    expect(result).toContain("contains(tolower(title), tolower('hello'))");
    expect(result).toContain(' or ');
  });

  it('joins multiple quick filter values with AND', () => {
    const result = convertQuickFilterToOData(['a', 'b'], ['name']);
    expect(result).toContain(' and ');
  });
});

describe('combineFiltersToOData', () => {
  it('returns empty for empty inputs', () => {
    expect(combineFiltersToOData({ items: [] })).toBe('');
  });

  it('returns only regular filter when no quick filter', () => {
    const result = combineFiltersToOData({
      items: [{ field: 'name', operator: 'contains', value: 'a', id: 1 }],
    });
    expect(result).toBe("contains(tolower(name), tolower('a'))");
  });

  it('combines regular and quick filters with AND', () => {
    const result = combineFiltersToOData(
      {
        items: [{ field: 'name', operator: 'contains', value: 'a', id: 1 }],
      },
      ['search'],
      ['title']
    );
    expect(result).toContain(') and (');
  });
});

// ---- Domain-specific quick filter functions ----

describe('convertTaskQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertTaskQuickFilterToOData([])).toBe('');
  });

  it('searches title and description fields', () => {
    const result = convertTaskQuickFilterToOData(['bug']);
    expect(result).toContain("contains(tolower(title), tolower('bug'))");
    expect(result).toContain("contains(tolower(description), tolower('bug'))");
    expect(result).toContain(' or ');
  });

  it('joins multiple values with AND', () => {
    const result = convertTaskQuickFilterToOData(['bug', 'fix']);
    expect(result).toContain(' and ');
  });

  it('skips empty values', () => {
    const result = convertTaskQuickFilterToOData(['', 'bug']);
    expect(result).toContain('bug');
    expect(result).not.toContain("tolower('')");
  });
});

describe('convertTestQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertTestQuickFilterToOData([])).toBe('');
  });

  it('searches test-related fields', () => {
    const result = convertTestQuickFilterToOData(['safety']);
    expect(result).toContain('prompt/content');
    expect(result).toContain('behavior/name');
    expect(result).toContain('topic/name');
    expect(result).toContain('category/name');
  });

  it('includes tags relationship search', () => {
    const result = convertTestQuickFilterToOData(['safety']);
    expect(result).toContain('_tags_relationship/any');
  });
});

describe('convertSourceQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertSourceQuickFilterToOData([])).toBe('');
  });

  it('searches title and description fields', () => {
    const result = convertSourceQuickFilterToOData(['docs']);
    expect(result).toContain("contains(tolower(title), tolower('docs'))");
    expect(result).toContain("contains(tolower(description), tolower('docs'))");
  });

  it('includes tags relationship search', () => {
    const result = convertSourceQuickFilterToOData(['docs']);
    expect(result).toContain('_tags_relationship/any');
  });
});

describe('convertTestRunQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertTestRunQuickFilterToOData([])).toBe('');
  });

  it('searches test run fields', () => {
    const result = convertTestRunQuickFilterToOData(['nightly']);
    expect(result).toContain("contains(tolower(name), tolower('nightly'))");
    expect(result).toContain('test_configuration/test_set/name');
    expect(result).toContain('user/name');
    expect(result).toContain('status/name');
  });

  it('includes tags relationship search', () => {
    const result = convertTestRunQuickFilterToOData(['nightly']);
    expect(result).toContain('_tags_relationship/any');
  });
});

describe('convertTestSetQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertTestSetQuickFilterToOData([])).toBe('');
  });

  it('searches test set fields', () => {
    const result = convertTestSetQuickFilterToOData(['regression']);
    expect(result).toContain("contains(tolower(name), tolower('regression'))");
    expect(result).toContain('user/name');
    expect(result).toContain('test_set_type/type_value');
  });

  it('includes tags relationship search', () => {
    const result = convertTestSetQuickFilterToOData(['regression']);
    expect(result).toContain('_tags_relationship/any');
  });
});

// ---- Domain-specific combine filter functions ----

describe('combineTaskFiltersToOData', () => {
  it('returns empty for empty filter model', () => {
    expect(combineTaskFiltersToOData({ items: [] })).toBe('');
  });

  it('converts regular task filter items', () => {
    const result = combineTaskFiltersToOData({
      items: [{ field: 'title', operator: 'contains', value: 'bug', id: 1 }],
    });
    expect(result).toContain("contains(tolower(title), tolower('bug'))");
  });

  it('separates quick filters and combines with regular', () => {
    const result = combineTaskFiltersToOData({
      items: [
        { field: 'title', operator: 'contains', value: 'bug', id: 1 },
        {
          field: '__quickFilter__',
          operator: 'contains',
          value: 'search',
          id: 2,
        },
      ],
    });
    expect(result).toContain('bug');
    expect(result).toContain('search');
    expect(result).toContain(' and ');
  });
});

describe('combineTestFiltersToOData', () => {
  it('returns empty for empty filter model', () => {
    expect(combineTestFiltersToOData({ items: [] })).toBe('');
  });

  it('converts a single regular filter', () => {
    const result = combineTestFiltersToOData({
      items: [{ field: 'name', operator: 'contains', value: 'bias', id: 1 }],
    });
    expect(result).toContain('bias');
  });

  it('separates quick filters from regular filters', () => {
    const result = combineTestFiltersToOData({
      items: [
        { field: 'name', operator: 'contains', value: 'test', id: 1 },
        {
          field: '__quickFilter__',
          operator: 'contains',
          value: 'search',
          id: 2,
        },
      ],
    });
    expect(result).toContain('test');
    expect(result).toContain('search');
  });
});

describe('combineSourceFiltersToOData', () => {
  it('returns empty for empty filter model', () => {
    expect(combineSourceFiltersToOData({ items: [] })).toBe('');
  });

  it('converts a single regular filter', () => {
    const result = combineSourceFiltersToOData({
      items: [{ field: 'title', operator: 'contains', value: 'readme', id: 1 }],
    });
    expect(result).toContain('readme');
  });

  it('handles quick filter items', () => {
    const result = combineSourceFiltersToOData({
      items: [
        { field: 'quickFilter', operator: 'contains', value: 'docs', id: 1 },
      ],
    });
    expect(result).toContain('docs');
  });
});

describe('combineTestRunFiltersToOData', () => {
  it('returns empty for empty filter model', () => {
    expect(combineTestRunFiltersToOData({ items: [] })).toBe('');
  });

  it('converts regular filters', () => {
    const result = combineTestRunFiltersToOData({
      items: [{ field: 'name', operator: 'contains', value: 'run-1', id: 1 }],
    });
    expect(result).toContain('run-1');
  });

  it('combines regular and quick filters', () => {
    const result = combineTestRunFiltersToOData({
      items: [
        { field: 'name', operator: 'contains', value: 'run', id: 1 },
        {
          field: '__quickFilter__',
          operator: 'contains',
          value: 'nightly',
          id: 2,
        },
      ],
    });
    expect(result).toContain('run');
    expect(result).toContain('nightly');
  });
});

describe('combineTestSetFiltersToOData', () => {
  it('returns empty for empty filter model', () => {
    expect(combineTestSetFiltersToOData({ items: [] })).toBe('');
  });

  it('converts regular test set filters with field mapping', () => {
    const result = combineTestSetFiltersToOData({
      items: [{ field: 'name', operator: 'contains', value: 'safety', id: 1 }],
    });
    expect(result).toContain('safety');
  });

  it('maps testSetType field to OData path', () => {
    const result = combineTestSetFiltersToOData({
      items: [
        { field: 'testSetType', operator: 'contains', value: 'manual', id: 1 },
      ],
    });
    expect(result).toContain('test_set_type/type_value');
  });

  it('maps creator field to user/name', () => {
    const result = combineTestSetFiltersToOData({
      items: [
        { field: 'creator', operator: 'contains', value: 'alice', id: 1 },
      ],
    });
    expect(result).toContain('user/name');
  });

  it('handles quick filter items', () => {
    const result = combineTestSetFiltersToOData({
      items: [
        {
          field: '__quickFilter__',
          operator: 'contains',
          value: 'regression',
          id: 1,
        },
      ],
    });
    expect(result).toContain('regression');
  });

  it('handles tags filter with relationship path', () => {
    const result = combineTestSetFiltersToOData({
      items: [
        { field: 'tags', operator: 'contains', value: 'important', id: 1 },
      ],
    });
    expect(result).toContain('_tags_relationship/any');
    expect(result).toContain('important');
  });
});
