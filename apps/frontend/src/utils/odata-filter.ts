import { GridFilterModel, GridFilterItem } from '@mui/x-data-grid';

import {
  memberJoinStatusActiveODataFilter,
  memberJoinStatusInvitedODataFilter,
} from './member-join-status';

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
    'requirement/name',
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

function convertRelationshipPresenceFilterToOData(
  relationship: string,
  operator: string
): string {
  switch (operator) {
    case 'isEmpty':
      return `not ${relationship}/any()`;
    case 'isNotEmpty':
      return `${relationship}/any()`;
    default:
      return '';
  }
}

function isPresenceOperator(operator: string | undefined): boolean {
  return operator === 'isEmpty' || operator === 'isNotEmpty';
}

function shouldSkipFilterItem(
  field: string | undefined,
  operator: string | undefined,
  value: unknown
): boolean {
  if (!field || !operator) return true;
  if (isPresenceOperator(operator)) return false;
  return value === undefined || value === null || value === '';
}

/**
 * Shared operator → OData expression switch. Every entity gets the same
 * operator support (standardized deliberately — narrower legacy subsets,
 * e.g. Test Sets not handling `>`/`>=`/`<`/`<=`, don't survive this
 * refactor: those grids just never emit those operators today, so this
 * only adds latent capability, it doesn't remove any tested behavior).
 */
function convertOperatorToOData(
  odataField: string,
  operator: string,
  value: unknown
): string {
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
 * Per-entity configuration for `convertConfiguredFilterItemToOData` /
 * `combineConfiguredFiltersToOData` — the field-map + special-case list
 * that used to be reimplemented per entity as a whole `convertXFilterItemToOData`
 * function. New entities should add a config here rather than a new function.
 */
export interface DirectoryFilterFieldConfig {
  /** Grid column field name → backend OData path. Unmapped fields fall
   *  through to `dotToSlashFallback`. */
  fieldMap?: Record<string, string>;
  /** Default true: an unmapped field with dots ('requirement.name') becomes
   *  OData path syntax ('requirement/name'). Tasks is the one entity that
   *  wants the literal field name instead, hence this being overridable. */
  dotToSlashFallback?: boolean;
  /** Field name treated as the tags many-to-many relationship. Pass `null`
   *  to disable tag handling for entities with no tags relationship
   *  (default: `'tags'`). */
  tagsField?: string | null;
  /** Field names treated as relationship-presence checks (`isEmpty`/
   *  `isNotEmpty` → `not X/any()` / `X/any()`) instead of a value
   *  comparison — e.g. `'comments'`, `'tasks'`. Default: none. */
  presenceFields?: string[];
}

function mapODataField(
  field: string,
  config: DirectoryFilterFieldConfig
): string {
  if (config.fieldMap?.[field]) return config.fieldMap[field];
  if (config.dotToSlashFallback === false) return field;
  return field.replace(/\./g, '/');
}

/**
 * Config-driven replacement for the family of `convertXFilterItemToOData`
 * functions (one per entity) that used to each reimplement this same
 * skip/tags/presence/field-map/operator pipeline from scratch.
 */
export function convertConfiguredFilterItemToOData(
  item: GridFilterItem,
  config: DirectoryFilterFieldConfig = {}
): string {
  const { field, operator, value } = item;

  if (shouldSkipFilterItem(field, operator, value)) {
    return '';
  }

  const tagsField = config.tagsField === undefined ? 'tags' : config.tagsField;
  if (tagsField && field === tagsField) {
    return convertTagsFilterToOData(item);
  }

  if (config.presenceFields?.includes(field)) {
    return convertRelationshipPresenceFilterToOData(field, operator as string);
  }

  const odataField = mapODataField(field as string, config);
  return convertOperatorToOData(odataField, operator as string, value);
}

/** Default config used by entities with no field remapping (Tests, Sources, Test Runs). */
const GENERIC_FILTER_CONFIG: DirectoryFilterFieldConfig = {
  tagsField: 'tags',
  presenceFields: ['comments', 'tasks'],
};

/**
 * Converts a MUI DataGrid filter item to an OData filter expression
 * Optimized for Tests filtering with simple navigation patterns
 */
function convertFilterItemToOData(item: GridFilterItem): string {
  return convertConfiguredFilterItemToOData(item, GENERIC_FILTER_CONFIG);
}

const TASK_FILTER_CONFIG: DirectoryFilterFieldConfig = {
  fieldMap: {
    status: 'status/name',
    assignee: 'assignee/name',
    priority: 'priority/type_value',
    user: 'user/name',
  },
  dotToSlashFallback: false,
};

/**
 * Escapes special characters in OData filter values
 */
export function escapeODataValue(value: unknown): string {
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
    .map(item => convertConfiguredFilterItemToOData(item, TASK_FILTER_CONFIG))
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
  return convertConfiguredQuickFilterToOData(quickFilterValues, {
    searchFields: searchFields ?? [],
  });
}

/**
 * Per-entity configuration for `convertConfiguredQuickFilterToOData` — the
 * search-fields list (+ optional extra clauses, e.g. a tags relationship
 * search) that used to be reimplemented per entity as a whole
 * `convertXQuickFilterToOData` function.
 */
export interface QuickFilterConfig {
  searchFields: string[];
  /** Extra OData clauses ORed in alongside `searchFields` for each quick-filter
   *  value — e.g. Tests/Sources/Test Sets additionally search the tags
   *  relationship, which isn't a plain field. */
  extraFieldExpressions?: (value: unknown) => string[];
}

/**
 * Config-driven replacement for the family of `convertXQuickFilterToOData`
 * functions (one per entity) that used to each reimplement this same
 * per-value OR-across-fields / AND-across-values pipeline from scratch.
 */
export function convertConfiguredQuickFilterToOData(
  quickFilterValues: unknown[],
  config: QuickFilterConfig
): string {
  if (
    !quickFilterValues ||
    quickFilterValues.length === 0 ||
    !config.searchFields ||
    config.searchFields.length === 0
  ) {
    return '';
  }

  const quickFilterExpressions = quickFilterValues
    .map(value => {
      if (!value || value === '') return '';

      const fieldConditions = config.searchFields.map(
        field =>
          `contains(tolower(${field}), tolower('${escapeODataValue(value)}'))`
      );
      if (config.extraFieldExpressions) {
        fieldConditions.push(...config.extraFieldExpressions(value));
      }

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

/** Config bundle for `combineConfiguredFiltersToOData`. */
export interface CombineFiltersConfig extends DirectoryFilterFieldConfig {
  quickFilter: QuickFilterConfig;
}

/**
 * Config-driven replacement for the family of `combineXFiltersToOData`
 * functions (one per entity) that used to each reimplement this same
 * split-quick-filter / convert-regular-items / join-with-logic-operator glue.
 */
export function combineConfiguredFiltersToOData(
  filterModel: GridFilterModel,
  config: CombineFiltersConfig
): string {
  if (!filterModel || !filterModel.items || filterModel.items.length === 0) {
    return '';
  }

  const regularFilters: GridFilterItem[] = [];
  const quickFilterValues: unknown[] = [];

  filterModel.items.forEach(item => {
    if (item.field === '__quickFilter__' || item.field === 'quickFilter') {
      quickFilterValues.push(item.value);
    } else {
      regularFilters.push(item);
    }
  });

  const regularFilterExpressions = regularFilters
    .map(item => convertConfiguredFilterItemToOData(item, config))
    .filter(expr => expr !== '');

  const quickFilterExpression =
    quickFilterValues.length > 0
      ? convertConfiguredQuickFilterToOData(
          quickFilterValues,
          config.quickFilter
        )
      : '';

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

  const logicOperator = filterModel.logicOperator === 'or' ? ' or ' : ' and ';
  return `(${allExpressions.join(logicOperator)})`;
}

const TASK_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: ['title', 'description'],
};

/**
 * Combines regular filters and quick filters into a single OData expression for tasks
 */
export function combineTaskFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...TASK_FILTER_CONFIG,
    quickFilter: TASK_QUICK_FILTER_CONFIG,
  });
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
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    TASK_QUICK_FILTER_CONFIG
  );
}

/** Appends a tags-relationship OR clause to a quick-filter value — shared by
 *  every entity whose quick search also matches on tag names (Tests, Sources,
 *  Test Sets, Test Runs). */
function tagsQuickFilterExpression(value: unknown): string[] {
  return [
    `_tags_relationship/any(t: contains(tolower(t/tag/name), tolower('${escapeODataValue(value)}')))`,
  ];
}

const TEST_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: [
    'prompt/content',
    'requirement/name',
    'topic/name',
    'category/name',
  ],
  extraFieldExpressions: tagsQuickFilterExpression,
};

/**
 * Handles quick filter (global search) conversion to OData for tests
 */
export function convertTestQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    TEST_QUICK_FILTER_CONFIG
  );
}

/**
 * Combines regular filters and quick filters into a single OData expression for tests
 */
export function combineTestFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...GENERIC_FILTER_CONFIG,
    quickFilter: TEST_QUICK_FILTER_CONFIG,
  });
}

const SOURCE_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: ['title', 'description'],
  extraFieldExpressions: tagsQuickFilterExpression,
};

/**
 * Handles quick filter (global search) conversion to OData for sources
 */
export function convertSourceQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    SOURCE_QUICK_FILTER_CONFIG
  );
}

/**
 * Combines regular filters and quick filters into a single OData expression for sources
 */
export function combineSourceFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...GENERIC_FILTER_CONFIG,
    quickFilter: SOURCE_QUICK_FILTER_CONFIG,
  });
}

const TEST_RUN_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: [
    'name',
    'test_configuration/test_set/name',
    'user/name',
    'status/name',
  ],
  extraFieldExpressions: tagsQuickFilterExpression,
};

/**
 * Handles quick filter (global search) conversion to OData for test runs
 */
export function convertTestRunQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    TEST_RUN_QUICK_FILTER_CONFIG
  );
}

/**
 * Combines regular filters and quick filters into a single OData expression for test runs
 */
export function combineTestRunFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...GENERIC_FILTER_CONFIG,
    quickFilter: TEST_RUN_QUICK_FILTER_CONFIG,
  });
}

/**
 * Converts a MUI DataGrid filter item to OData for test sets.
 * Maps grid field names to backend OData paths (name, testSetType->test_set_type/type_value,
 * creator->user/name, tags->_tags_relationship).
 */
const TEST_SET_FILTER_CONFIG: DirectoryFilterFieldConfig = {
  fieldMap: {
    testSetType: 'test_set_type/type_value',
    creator: 'user/name',
  },
  ...GENERIC_FILTER_CONFIG,
};

const TEST_SET_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: ['name', 'user/name', 'test_set_type/type_value'],
  extraFieldExpressions: tagsQuickFilterExpression,
};

/**
 * Handles quick filter (global search) conversion to OData for test sets
 */
export function convertTestSetQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    TEST_SET_QUICK_FILTER_CONFIG
  );
}

/**
 * Combines regular filters and quick filters into a single OData expression for test sets
 */
export function combineTestSetFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...TEST_SET_FILTER_CONFIG,
    quickFilter: TEST_SET_QUICK_FILTER_CONFIG,
  });
}

const EXPERIMENT_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: ['name', 'description', 'visibility', 'project/name'],
};

const EXPERIMENT_FILTER_CONFIG: DirectoryFilterFieldConfig = {
  fieldMap: { projectName: 'project/name' },
  ...GENERIC_FILTER_CONFIG,
};

/**
 * Combines regular filters and quick filters into a single OData
 * expression for experiments.
 */
export function combineExperimentFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...EXPERIMENT_FILTER_CONFIG,
    quickFilter: EXPERIMENT_QUICK_FILTER_CONFIG,
  });
}

const ENDPOINT_QUICK_FILTER_CONFIG: QuickFilterConfig = {
  searchFields: ['name', 'environment', 'connection_type', 'description'],
};

/**
 * Handles quick filter (global search) conversion to OData for endpoints
 */
export function convertEndpointQuickFilterToOData(
  quickFilterValues: unknown[]
): string {
  return convertConfiguredQuickFilterToOData(
    quickFilterValues,
    ENDPOINT_QUICK_FILTER_CONFIG
  );
}

const ENDPOINT_FILTER_CONFIG: DirectoryFilterFieldConfig = {
  fieldMap: {
    connectionType: 'connection_type',
    projectId: 'project_id',
    status: 'status/name',
  },
};

/**
 * Combines regular filters and quick filters into a single OData expression for endpoints
 */
export function combineEndpointFiltersToOData(
  filterModel: GridFilterModel
): string {
  return combineConfiguredFiltersToOData(filterModel, {
    ...ENDPOINT_FILTER_CONFIG,
    quickFilter: ENDPOINT_QUICK_FILTER_CONFIG,
  });
}

/**
 * Builds the full OData filter for endpoint list queries, optionally scoped to a project.
 */
export function buildEndpointListFilter(
  filterModel: GridFilterModel,
  projectId?: string
): string {
  const parts: string[] = [];

  if (projectId) {
    parts.push(`project_id eq '${escapeODataValue(projectId)}'`);
  }

  const combined = combineEndpointFiltersToOData(filterModel);
  if (combined) {
    parts.push(combined);
  }

  if (parts.length === 0) {
    return '';
  }
  if (parts.length === 1) {
    return parts[0];
  }
  return `(${parts.join(') and (')})`;
}

// ── Team member filters (organization team page) ─────────────────────────────

export interface TeamFilters {
  /** Joined vs pending invite — mapped to joined_at OData checks */
  memberStatus: '' | 'active' | 'invited';
  /** Account enabled flag — null means no filter */
  accountStatus: boolean | null;
  email: string;
  name: string;
}

export const EMPTY_TEAM_FILTERS: TeamFilters = {
  memberStatus: '',
  accountStatus: null,
  email: '',
  name: '',
};

export function hasActiveTeamFilters(f: TeamFilters): boolean {
  return (
    f.memberStatus !== '' ||
    f.accountStatus !== null ||
    f.email.trim() !== '' ||
    f.name.trim() !== ''
  );
}

export function countActiveTeamFilters(f: TeamFilters): number {
  return (
    (f.memberStatus !== '' ? 1 : 0) +
    (f.accountStatus !== null ? 1 : 0) +
    (f.email.trim() !== '' ? 1 : 0) +
    (f.name.trim() !== '' ? 1 : 0)
  );
}

/**
 * Builds OData $filter for team member list queries (search pill + drawer).
 */
export function combineTeamFiltersToOData(
  searchQuery: string,
  drawerFilters: TeamFilters
): string | undefined {
  const parts: string[] = [];

  const search = searchQuery.trim();
  if (search) {
    const q = escapeODataValue(search);
    parts.push(
      `(contains(email,'${q}') or contains(name,'${q}') or contains(given_name,'${q}') or contains(family_name,'${q}'))`
    );
  }

  const email = drawerFilters.email.trim();
  if (email) {
    parts.push(`contains(email,'${escapeODataValue(email)}')`);
  }

  const name = drawerFilters.name.trim();
  if (name) {
    const n = escapeODataValue(name);
    parts.push(
      `(contains(name,'${n}') or contains(given_name,'${n}') or contains(family_name,'${n}'))`
    );
  }

  if (drawerFilters.memberStatus === 'active') {
    parts.push(memberJoinStatusActiveODataFilter());
  } else if (drawerFilters.memberStatus === 'invited') {
    parts.push(memberJoinStatusInvitedODataFilter());
  }

  if (drawerFilters.accountStatus === true) {
    parts.push('is_active eq true');
  } else if (drawerFilters.accountStatus === false) {
    parts.push('is_active eq false');
  }

  if (parts.length === 0) {
    return undefined;
  }
  if (parts.length === 1) {
    return parts[0];
  }
  return parts.map(p => `(${p})`).join(' and ');
}
