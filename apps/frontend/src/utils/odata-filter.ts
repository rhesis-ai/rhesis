import { GridFilterModel, GridFilterItem } from '@mui/x-data-grid';

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
    'owner/family_name'
  ];

  // Create contains conditions for each field
  const conditions = searchableFields.map(field => 
    `contains(tolower(${field}), tolower('${escapedTerm}'))`
  );

  // Join all conditions with OR
  return conditions.join(' or ');
}

/**
 * Converts a MUI DataGrid filter item to an OData filter expression
 * Optimized for Tests filtering with simple navigation patterns
 */
function convertFilterItemToOData(item: GridFilterItem): string {
  const { field, operator, value } = item;
  
  if (!field || !operator || value === undefined || value === null || value === '') {
    return '';
  }

  // Convert dot notation to OData relationship syntax
  // e.g., 'behavior.name' becomes 'behavior/name'
  let odataField = field.replace(/\./g, '/');

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
      return `${odataField} eq null`;
    
    case 'isNotEmpty':
      return `${odataField} ne null`;
    
    default:
      console.warn(`Unsupported operator: ${operator}`);
      return '';
  }
}

/**
 * Escapes special characters in OData filter values
 */
function escapeODataValue(value: any): string {
  if (typeof value !== 'string') {
    return String(value);
  }
  
  // Escape single quotes by doubling them
  return value.replace(/'/g, "''");
}

/**
 * Converts a MUI DataGrid filter model to an OData filter expression
 * Optimized for Tests filtering
 */
export function convertGridFilterModelToOData(filterModel: GridFilterModel): string {
  if (!filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  const filterExpressions = filterModel.items
    .map(item => convertFilterItemToOData(item))
    .filter(expr => expr !== '');

  if (filterExpressions.length === 0) {
    return '';
  }

  // Join multiple filters with AND (MUI DataGrid typically uses AND by default)
  // Note: linkOperator might not be available in all versions, so we default to 'and'
  const linkOperator = (filterModel as any).linkOperator || 'and';
  return filterExpressions.join(` ${linkOperator} `);
} 