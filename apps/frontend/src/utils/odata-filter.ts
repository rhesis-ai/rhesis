import { GridFilterModel, GridFilterItem } from '@mui/x-data-grid';

/**
 * Creates a wildcard search filter for tasks that searches across all major text fields
 * This simulates a $search functionality by using OR conditions across multiple fields
 */
export function createTaskWildcardSearchFilter(searchTerm: string): string {
  if (!searchTerm || searchTerm.trim() === '') {
    return '';
  }

  const escapedTerm = escapeODataValue(searchTerm.trim());

  // Define all the searchable fields for tasks - only title and description
  const searchableFields = ['title', 'description'];

  // Create contains conditions for each field
  const conditions = searchableFields.map(
    field => `contains(tolower(${field}), tolower('${escapedTerm}'))`
  );

  // Join all conditions with OR
  return conditions.join(' or ');
}

/**
 * Creates a wildcard search filter that searches across all major text fields
 * This simulates a $search functionality by using OR conditions across multiple fields
 */
export function createWildcardSearchFilter(searchTerm: string): string {
  if (!searchTerm || searchTerm.trim() === '') {
    return '';
  }

  const escapedTerm = escapeODataValue(searchTerm.trim());

  // Define all the searchable fields for tests
  const searchableFields = [
    'behavior/name',
    'topic/name',
    'category/name',
    'prompt/content',
    'assignee/name',
    'assignee/email',
    'assignee/given_name',
    'assignee/family_name',
    'owner/name',
    'owner/email',
    'owner/given_name',
    'owner/family_name',
  ];

  // Create contains conditions for each field
  const conditions = searchableFields.map(
    field => `contains(tolower(${field}), tolower('${escapedTerm}'))`
  );

  // Join all conditions with OR
  return conditions.join(' or ');
}

/**
 * Converts a tags filter item to OData expression
 * Tags are a many-to-many relationship through TaggedItem, so we need special handling
 * The actual relationship is _tags_relationship which points to TaggedItem,
 * and TaggedItem has a tag relationship that points to Tag
 */
function convertTagsFilterToOData(item: GridFilterItem): string {
  const { operator, value } = item;

  if (!operator || value === undefined || value === null || value === '') {
    return '';
  }

  // Handle different operators for tags
  // Use the actual SQLAlchemy relationship path: _tags_relationship/tag/name
  switch (operator) {
    case 'contains':
      // For contains, check if any tag name contains the value
      return `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`;

    case 'equals':
    case '=':
    case 'is':
      // For exact match, check if any tag name equals the value
      if (typeof value === 'string') {
        return `_tags_relationship/any(t: tolower(t/tag/name) eq tolower('${escapeODataValue(value)}'))`;
      }
      return `_tags_relationship/any(t: t/tag/name eq '${escapeODataValue(value)}')`;

    case 'isAnyOf':
      // For isAnyOf, check if any tag name matches any of the values
      if (Array.isArray(value) && value.length > 0) {
        const conditions = value
          .map(
            v =>
              `_tags_relationship/any(t: tolower(t/tag/name) eq tolower('${escapeODataValue(v)}'))`
          )
          .join(' or ');
        return `(${conditions})`;
      }
      return '';

    case 'isEmpty':
      return 'not _tags_relationship/any()';

    case 'isNotEmpty':
      return '_tags_relationship/any()';

    default:
      // Fallback to contains for unknown operators
      return `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`;
  }
}

/**
 * Converts a MUI DataGrid filter item to an OData filter expression
 * Optimized for Tests filtering with simple navigation patterns
 */
function convertFilterItemToOData(item: GridFilterItem): string {
  const { field, operator, value } = item;

  if (
    !field ||
    !operator ||
    value === undefined ||
    value === null ||
    value === ''
  ) {
    return '';
  }

  // Special handling for tags field - use the relationship path
  if (field === 'tags') {
    return convertTagsFilterToOData(item);
  }

  // Convert dot notation to OData relationship syntax
  // e.g., 'behavior.name' becomes 'behavior/name'
  const odataField = field.replace(/\./g, '/');

  // Handle different operators following the official OData guide patterns
  switch (operator) {
    case 'contains':
      return `contains(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'startsWith':
      return `startswith(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'endsWith':
      return `endswith(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'equals':
    case '=':
    case 'is':
      // For string fields, use case-insensitive comparison
      if (typeof value === 'string') {
        return `tolower(${odataField}) eq tolower('${escapeODataValue(value)}')`;
      }
      return `${odataField} eq '${escapeODataValue(value)}'`;

    case 'not':
    case '!=':
      // For string fields, use case-insensitive comparison
      if (typeof value === 'string') {
        return `tolower(${odataField}) ne tolower('${escapeODataValue(value)}')`;
      }
      return `${odataField} ne '${escapeODataValue(value)}'`;

    case 'greaterThan':
    case '>':
      return `${odataField} gt ${escapeODataValue(value)}`;

    case 'greaterThanOrEqual':
    case '>=':
      return `${odataField} ge ${escapeODataValue(value)}`;

    case 'lessThan':
    case '<':
      return `${odataField} lt ${escapeODataValue(value)}`;

    case 'lessThanOrEqual':
    case '<=':
      return `${odataField} le ${escapeODataValue(value)}`;

    case 'isEmpty':
      return `${odataField} eq null or ${odataField} eq ''`;

    case 'isNotEmpty':
      return `${odataField} ne null and ${odataField} ne ''`;

    case 'isAnyOf':
      if (Array.isArray(value) && value.length > 0) {
        const conditions = value
          .map(v => `${odataField} eq '${escapeODataValue(v)}'`)
          .join(' or ');
        return `(${conditions})`;
      }
      return '';

    default:
      // Fallback for unknown operators - treat as contains
      return `contains(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;
  }
}

/**
 * Converts a MUI DataGrid filter item to an OData filter expression
 * Optimized for Tasks filtering with proper field mapping
 */
function convertTaskFilterItemToOData(item: GridFilterItem): string {
  const { field, operator, value } = item;

  if (
    !field ||
    !operator ||
    value === undefined ||
    value === null ||
    value === ''
  ) {
    return '';
  }

  // Handle quick filter (global search) - MUI DataGrid adds this as a special field
  if (field === '__quickFilter__' || field === 'quickFilter') {
    return convertTaskQuickFilterToOData([value]);
  }

  // Special handling for tags field - use the relationship path
  if (field === 'tags') {
    return convertTagsFilterToOData(item);
  }

  // Map task-specific fields to their OData relationship syntax
  let odataField = field;

  // Handle relationship fields
  switch (field) {
    case 'status':
      odataField = 'status/name';
      break;
    case 'assignee':
      odataField = 'assignee/name';
      break;
    case 'priority':
      odataField = 'priority/type_value';
      break;
    case 'user':
      odataField = 'user/name';
      break;
    default:
      // For direct fields like 'title', 'description', keep as is
      odataField = field;
  }

  // Handle different operators following the official OData guide patterns
  switch (operator) {
    case 'contains':
      return `contains(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'startsWith':
      return `startswith(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'endsWith':
      return `endswith(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;

    case 'equals':
    case '=':
    case 'is':
      // For string fields, use case-insensitive comparison
      if (typeof value === 'string') {
        return `tolower(${odataField}) eq tolower('${escapeODataValue(value)}')`;
      }
      return `${odataField} eq '${escapeODataValue(value)}'`;

    case 'not':
    case '!=':
      // For string fields, use case-insensitive comparison
      if (typeof value === 'string') {
        return `tolower(${odataField}) ne tolower('${escapeODataValue(value)}')`;
      }
      return `${odataField} ne '${escapeODataValue(value)}'`;

    case 'greaterThan':
    case '>':
      return `${odataField} gt ${escapeODataValue(value)}`;

    case 'greaterThanOrEqual':
    case '>=':
      return `${odataField} ge ${escapeODataValue(value)}`;

    case 'lessThan':
    case '<':
      return `${odataField} lt ${escapeODataValue(value)}`;

    case 'lessThanOrEqual':
    case '<=':
      return `${odataField} le ${escapeODataValue(value)}`;

    case 'isEmpty':
      return `${odataField} eq null or ${odataField} eq ''`;

    case 'isNotEmpty':
      return `${odataField} ne null and ${odataField} ne ''`;

    case 'isAnyOf':
      if (Array.isArray(value) && value.length > 0) {
        const conditions = value
          .map(v => `${odataField} eq '${escapeODataValue(v)}'`)
          .join(' or ');
        return `(${conditions})`;
      }
      return '';

    default:
      // Fallback for unknown operators - treat as contains
      return `contains(tolower(${odataField}), tolower('${escapeODataValue(value)}'))`;
  }
}

/**
 * Escapes special characters in OData filter values
 */
function escapeODataValue(value: unknown): string {
  if (typeof value !== 'string') {
    return String(value);
  }

  // Escape single quotes by doubling them
  return value.replace(/'/g, "''");
}

/**
 * Converts a MUI DataGrid filter model to an OData filter expression
 * Optimized for Tasks filtering
 */
export function convertTaskFilterModelToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Convert each filter item to OData expression using task-specific converter
  const filterExpressions = filterModel.items
    .map(item => convertTaskFilterItemToOData(item))
    .filter(expr => expr !== ''); // Remove empty expressions

  if (filterExpressions.length === 0) {
    return '';
  }

  if (filterExpressions.length === 1) {
    return filterExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${filterExpressions.join(logicOperator)})`;
}

/**
 * Converts a MUI DataGrid filter model to an OData filter expression
 * Optimized for Tests filtering
 */
export function convertGridFilterModelToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Convert each filter item to OData expression
  const filterExpressions = filterModel.items
    .map(item => convertFilterItemToOData(item))
    .filter(expr => expr !== ''); // Remove empty expressions

  if (filterExpressions.length === 0) {
    return '';
  }

  if (filterExpressions.length === 1) {
    return filterExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${filterExpressions.join(logicOperator)})`;
}

/**
 * Handles quick filter (global search) conversion to OData
 */
export function convertQuickFilterToOData(
  quickFilterValues: unknown[],
  searchFields: string[]
): string {
  if (
    !quickFilterValues ||
    quickFilterValues.length === 0 ||
    !searchFields ||
    searchFields.length === 0
  ) {
    return '';
  }

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      // Create a contains condition for each search field
      const fieldConditions = searchFields.map(
        field =>
          `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
      );

      // Join field conditions with OR (search in any field)
      return `(${fieldConditions.join(' or ')})`;
    })
    .filter(expr => expr !== '');

  if (quickFilterExpressions.length === 0) {
    return '';
  }

  if (quickFilterExpressions.length === 1) {
    return quickFilterExpressions[0];
  }

  // Join multiple quick filter values with AND (all values must match)
  return `(${quickFilterExpressions.join(' and ')})`;
}

/**
 * Combines regular filters and quick filters into a single OData expression for tasks
 */
export function combineTaskFiltersToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Separate regular filters from quick filters
  const regularFilters: GridFilterItem[] = [];
  const quickFilterValues: unknown[] = [];

  filterModel.items.forEach(item => {
    if (item.field === '__quickFilter__' || item.field === 'quickFilter') {
      quickFilterValues.push(item.value);
    } else {
      regularFilters.push(item);
    }
  });

  // Convert regular filters
  const regularFilterExpressions = regularFilters
    .map(item => convertTaskFilterItemToOData(item))
    .filter(expr => expr !== '');

  // Convert quick filters
  const quickFilterExpression =
    quickFilterValues.length > 0
      ? convertTaskQuickFilterToOData(quickFilterValues)
      : '';

  // Combine both types of filters
  const allExpressions = [...regularFilterExpressions];
  if (quickFilterExpression) {
    allExpressions.push(quickFilterExpression);
  }

  if (allExpressions.length === 0) {
    return '';
  }

  if (allExpressions.length === 1) {
    return allExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${allExpressions.join(logicOperator)})`;
}

/**
 * Combines regular filters and quick filters into a single OData expression
 */
export function combineFiltersToOData(
  filterModel: GridFilterModel,
  quickFilterValues?: unknown[],
  searchFields?: string[]
): string {
  const regularFilter = convertGridFilterModelToOData(filterModel);
  const quickFilter =
    quickFilterValues && searchFields
      ? convertQuickFilterToOData(quickFilterValues, searchFields)
      : '';

  if (regularFilter && quickFilter) {
    return `(${regularFilter}) and (${quickFilter})`;
  }

  return regularFilter || quickFilter || '';
}

/**
 * Handles quick filter (global search) conversion to OData for tasks
 */
export function convertTaskQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  if (!quickFilterValues || quickFilterValues.length === 0) {
    return '';
  }

  // Define task searchable fields - only title and description
  const searchFields = ['title', 'description'];

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      // Create a contains condition for each search field
      const fieldConditions = searchFields.map(
        field =>
          `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
      );

      // Join field conditions with OR (search in any field)
      return `(${fieldConditions.join(' or ')})`;
    })
    .filter(expr => expr !== '');

  if (quickFilterExpressions.length === 0) {
    return '';
  }

  if (quickFilterExpressions.length === 1) {
    return quickFilterExpressions[0];
  }

  // Join multiple quick filter values with AND (all values must match)
  return `(${quickFilterExpressions.join(' and ')})`;
}

/**
 * Handles quick filter (global search) conversion to OData for tests
 */
export function convertTestQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  if (!quickFilterValues || quickFilterValues.length === 0) {
    return '';
  }

  // Define test searchable fields - based on TestsGrid columns
  const searchFields = [
    'prompt/content',
    'behavior/name',
    'topic/name',
    'category/name',
  ];

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      // Create a contains condition for each search field
      const fieldConditions = searchFields.map(
        field =>
          `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
      );

      // Add tags search with proper relationship path
      fieldConditions.push(
        `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`
      );

      // Join field conditions with OR (search in any field)
      return `(${fieldConditions.join(' or ')})`;
    })
    .filter(expr => expr !== '');

  if (quickFilterExpressions.length === 0) {
    return '';
  }

  if (quickFilterExpressions.length === 1) {
    return quickFilterExpressions[0];
  }

  // Join multiple quick filter values with AND (all values must match)
  return `(${quickFilterExpressions.join(' and ')})`;
}

/**
 * Combines regular filters and quick filters into a single OData expression for tests
 */
export function combineTestFiltersToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Separate regular filters from quick filters
  const regularFilters: GridFilterItem[] = [];
  const quickFilterValues: unknown[] = [];

  filterModel.items.forEach(item => {
    if (item.field === '__quickFilter__' || item.field === 'quickFilter') {
      quickFilterValues.push(item.value);
    } else {
      regularFilters.push(item);
    }
  });

  // Convert regular filters (tags handling is now in convertFilterItemToOData)
  const regularFilterExpressions = regularFilters
    .map(item => convertFilterItemToOData(item))
    .filter(expr => expr !== '');

  // Convert quick filters
  const quickFilterExpression =
    quickFilterValues.length > 0
      ? convertTestQuickFilterToOData(quickFilterValues)
      : '';

  // Combine both types of filters
  const allExpressions = [...regularFilterExpressions];
  if (quickFilterExpression) {
    allExpressions.push(quickFilterExpression);
  }

  if (allExpressions.length === 0) {
    return '';
  }

  if (allExpressions.length === 1) {
    return allExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${allExpressions.join(logicOperator)})`;
}

/**
 * Handles quick filter (global search) conversion to OData for sources
 */
export function convertSourceQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  if (!quickFilterValues || quickFilterValues.length === 0) {
    return '';
  }

  // Define source searchable fields - title and description
  const searchFields = ['title', 'description'];

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      // Create a contains condition for each search field
      const fieldConditions = searchFields.map(
        field =>
          `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
      );

      // Add tags search with proper relationship path
      fieldConditions.push(
        `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`
      );

      // Join field conditions with OR (search in any field)
      return `(${fieldConditions.join(' or ')})`;
    })
    .filter(expr => expr !== '');

  if (quickFilterExpressions.length === 0) {
    return '';
  }

  if (quickFilterExpressions.length === 1) {
    return quickFilterExpressions[0];
  }

  // Join multiple quick filter values with AND (all values must match)
  return `(${quickFilterExpressions.join(' and ')})`;
}

/**
 * Combines regular filters and quick filters into a single OData expression for sources
 */
export function combineSourceFiltersToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Separate regular filters from quick filters
  const regularFilters: GridFilterItem[] = [];
  const quickFilterValues: unknown[] = [];

  filterModel.items.forEach(item => {
    if (item.field === '__quickFilter__' || item.field === 'quickFilter') {
      quickFilterValues.push(item.value);
    } else {
      regularFilters.push(item);
    }
  });

  // Convert regular filters (tags handling is now in convertFilterItemToOData)
  const regularFilterExpressions = regularFilters
    .map(item => convertFilterItemToOData(item))
    .filter(expr => expr !== '');

  // Convert quick filters
  const quickFilterExpression =
    quickFilterValues.length > 0
      ? convertSourceQuickFilterToOData(quickFilterValues)
      : '';

  // Combine both types of filters
  const allExpressions = [...regularFilterExpressions];
  if (quickFilterExpression) {
    allExpressions.push(quickFilterExpression);
  }

  if (allExpressions.length === 0) {
    return '';
  }

  if (allExpressions.length === 1) {
    return allExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${allExpressions.join(logicOperator)})`;
}

/**
 * Handles quick filter (global search) conversion to OData for test runs
 */
export function convertTestRunQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  if (!quickFilterValues || quickFilterValues.length === 0) {
    return '';
  }

  // Define test run searchable fields
  const searchFields = [
    'name',
    'test_configuration/test_set/name',
    'user/name',
    'status/name',
    'tags/name', // Search in tag names
  ];

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      // Create a contains condition for each search field
      const fieldConditions = searchFields.map(field => {
        // Special handling for tags field (collection through TaggedItem)
        if (field === 'tags/name') {
          return `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`;
        }
        // Regular fields
        return `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`;
      });

      // Join field conditions with OR (search in any field)
      return `(${fieldConditions.join(' or ')})`;
    })
    .filter(expr => expr !== '');

  if (quickFilterExpressions.length === 0) {
    return '';
  }

  if (quickFilterExpressions.length === 1) {
    return quickFilterExpressions[0];
  }

  // Join multiple quick filter values with AND (all values must match)
  return `(${quickFilterExpressions.join(' and ')})`;
}

/**
 * Combines regular filters and quick filters into a single OData expression for test runs
 */
export function combineTestRunFiltersToOData(
  filterModel: GridFilterModel
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  // Separate regular filters from quick filters
  const regularFilters: GridFilterItem[] = [];
  const quickFilterValues: unknown[] = [];

  filterModel.items.forEach(item => {
    if (item.field === '__quickFilter__' || item.field === 'quickFilter') {
      quickFilterValues.push(item.value);
    } else {
      regularFilters.push(item);
    }
  });

  // Convert regular filters (tags handling is now in convertFilterItemToOData)
  const regularFilterExpressions = regularFilters
    .map(item => convertFilterItemToOData(item))
    .filter(expr => expr !== '');

  // Convert quick filters
  const quickFilterExpression =
    quickFilterValues.length > 0
      ? convertTestRunQuickFilterToOData(quickFilterValues)
      : '';

  // Combine both types of filters
  const allExpressions = [...regularFilterExpressions];
  if (quickFilterExpression) {
    allExpressions.push(quickFilterExpression);
  }

  if (allExpressions.length === 0) {
    return '';
  }

  if (allExpressions.length === 1) {
    return allExpressions[0];
  }

  // Join multiple filters with the logic operator
  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${allExpressions.join(logicOperator)})`;
}
