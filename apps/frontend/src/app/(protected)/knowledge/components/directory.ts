import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineDirectory } from '@/utils/directory';
import { escapeODataValue } from '@/utils/odata-filter';

const SOURCES_FILTERS = {
  search: {
    kind: 'search',
    columns: ['title', 'description'],
    navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
  },
  sourceType: { kind: 'enum', column: 'source_type/type_value' },
  // `contains`, not `eq` -- matches the old builder's operator for this field.
  creator: {
    kind: 'raw',
    toOData: (value: string) =>
      value.trim()
        ? `contains(tolower(user/name),tolower('${escapeODataValue(value.trim())}'))`
        : undefined,
  },
  tag: {
    kind: 'raw',
    toOData: (value: string) =>
      value.trim()
        ? `_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('${escapeODataValue(value.trim())}')))`
        : undefined,
  },
} as const;

export const sourcesDirectory = defineDirectory({
  title: 'Knowledge',
  resource: 'knowledge sources',
  capability: Capability.Source.READ,
  defaultPageSize: 25,
  filters: SOURCES_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getSourcesClient().getSources(params),
});
