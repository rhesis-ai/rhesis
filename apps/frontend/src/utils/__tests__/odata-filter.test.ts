import {
  createWildcardSearchFilter,
  createTaskWildcardSearchFilter,
  convertGridFilterModelToOData,
  convertTaskFilterModelToOData,
  convertQuickFilterToOData,
  combineFiltersToOData,
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
      logicOperator: 'or',
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
