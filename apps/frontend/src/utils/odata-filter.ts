import { GridFilterModel, GridFilterItem } from '@mui/x-data-grid';

/**
 * Converts a MUI DataGrid filter item to an OData filter expression
 */
function convertFilterItemToOData(item: GridFilterItem): string {
  const { field, operator, value } = item;
  
  if (!field || !operator || value === undefined || value === null || value === '') {
    return '';
  }

  // Convert dot notation to OData relationship syntax
  // e.g., 'behavior.name' becomes 'behavior/name'
  const odataField = field.replace(/\./g, '/');

  // Handle different operators
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
      return `${odataField} eq '${escapeODataValue(value)}'`;
    
    case 'not':
    case '!=':
      return `${odataField} ne '${escapeODataValue(value)}'`;
    
    case '>':
      return `${odataField} gt '${escapeODataValue(value)}'`;
    
    case '>=':
      return `${odataField} ge '${escapeODataValue(value)}'`;
    
    case '<':
      return `${odataField} lt '${escapeODataValue(value)}'`;
    
    case '<=':
      return `${odataField} le '${escapeODataValue(value)}'`;
    
    case 'isEmpty':
      return `${odataField} eq null or ${odataField} eq ''`;
    
    case 'isNotEmpty':
      return `${odataField} ne null and ${odataField} ne ''`;
    
    case 'isAnyOf':
      if (Array.isArray(value) && value.length > 0) {
        const conditions = value.map(v => `${odataField} eq '${escapeODataValue(v)}'`).join(' or ');
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
function escapeODataValue(value: any): string {
  if (typeof value !== 'string') {
    return String(value);
  }
  
  // Escape single quotes by doubling them
  return value.replace(/'/g, "''");
}

/**
 * Converts a MUI DataGrid GridFilterModel to an OData $filter expression
 */
export function convertGridFilterModelToOData(filterModel: GridFilterModel): string {
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
export function convertQuickFilterToOData(quickFilterValues: any[], searchFields: string[]): string {
  if (!quickFilterValues || quickFilterValues.length === 0 || !searchFields || searchFields.length === 0) {
    return '';
  }

  const quickFilterExpressions = quickFilterValues.map(value => {
    if (!value || value === '') return '';
    
    // Create a contains condition for each search field
    const fieldConditions = searchFields.map(field => 
      `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
    );
    
    // Join field conditions with OR (search in any field)
    return `(${fieldConditions.join(' or ')})`;
  }).filter(expr => expr !== '');

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
 * Combines regular filters and quick filters into a single OData expression
 */
export function combineFiltersToOData(
  filterModel: GridFilterModel, 
  quickFilterValues?: any[], 
  searchFields?: string[]
): string {
  const regularFilter = convertGridFilterModelToOData(filterModel);
  const quickFilter = quickFilterValues && searchFields 
    ? convertQuickFilterToOData(quickFilterValues, searchFields) 
    : '';

  if (regularFilter && quickFilter) {
    return `(${regularFilter}) and (${quickFilter})`;
  }

  return regularFilter || quickFilter || '';
} 