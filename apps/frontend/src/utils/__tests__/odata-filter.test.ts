import { GridLogicOperator } from '@mui/x-data-grid';
import {
  createWildcardSearchFilter,
  convertGridFilterModelToOData,
  convertQuickFilterToOData,
  combineFiltersToOData,
  convertTestQuickFilterToOData,
  combineTestFiltersToOData,
} from '../odata-filter';

describe('createWildcardSearchFilter', () => {
  it('returns empty string for empty input', () => {
    expect(createWildcardSearchFilter('')).toBe('');
  });

  it('creates filter for test-related fields', () => {
    const result = createWildcardSearchFilter('query');
    expect(result).toContain('requirement/name');
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
          field: 'requirement.name',
          operator: 'contains',
          value: 'test',
          id: 1,
        },
      ],
    });
    expect(result).toContain('requirement/name');
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

describe('convertTestQuickFilterToOData', () => {
  it('returns empty string for empty values', () => {
    expect(convertTestQuickFilterToOData([])).toBe('');
  });

  it('searches test-related fields', () => {
    const result = convertTestQuickFilterToOData(['safety']);
    expect(result).toContain('prompt/content');
    expect(result).toContain('requirement/name');
    expect(result).toContain('topic/name');
    expect(result).toContain('category/name');
  });

  it('includes tags relationship search', () => {
    const result = convertTestQuickFilterToOData(['safety']);
    expect(result).toContain('_tags_relationship/any');
  });
});

// ---- Domain-specific combine filter functions ----

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

  it('converts tag, comment, and task presence filters', () => {
    const withTags = combineTestFiltersToOData({
      items: [{ field: 'tags', operator: 'isNotEmpty', value: true, id: 1 }],
    });
    expect(withTags).toBe('_tags_relationship/any()');

    const withoutComments = combineTestFiltersToOData({
      items: [{ field: 'comments', operator: 'isEmpty', value: true, id: 1 }],
    });
    expect(withoutComments).toBe('not comments/any()');

    const withTasks = combineTestFiltersToOData({
      items: [{ field: 'tasks', operator: 'isNotEmpty', value: true, id: 1 }],
    });
    expect(withTasks).toBe('tasks/any()');
  });
});
