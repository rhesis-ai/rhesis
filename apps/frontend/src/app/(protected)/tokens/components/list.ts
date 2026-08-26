import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

/** OData datetime literal for "now" -- unquoted ISO, matching the jobs date filters. */
function nowLiteral(): string {
  return new Date().toISOString();
}

const TOKENS_FILTERS = {
  search: { kind: 'search', columns: ['name', 'token_obfuscated'] },
  // A token without expires_at never expires.
  status: {
    kind: 'raw',
    toOData: (value: string) => {
      if (value === 'active')
        return `(expires_at eq null or expires_at gt ${nowLiteral()})`;
      if (value === 'expired') return `expires_at le ${nowLiteral()}`;
      return undefined;
    },
  },
  usage: {
    kind: 'raw',
    toOData: (value: string) => {
      if (value === 'used') return 'last_used_at ne null';
      if (value === 'never_used') return 'last_used_at eq null';
      return undefined;
    },
  },
} as const;

export const tokensList = defineList({
  title: 'API Tokens',
  resource: 'API tokens',
  capability: Capability.Token.MANAGE,
  defaultPageSize: 10,
  filters: TOKENS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getTokensClient().listTokens(params),
  delete: {
    bulk: (factory: ApiClientFactory, ids: string[]) =>
      factory.getTokensClient().bulkDeleteTokens(ids),
    capability: Capability.Token.MANAGE,
    capabilityMode: 'ambient',
    labelSingular: 'token',
    labelPlural: 'tokens',
    confirmMessage: count =>
      count === 1
        ? 'Are you sure you want to delete this token? This action cannot be undone, and any applications using this token will no longer be able to authenticate.'
        : `Are you sure you want to delete ${count} tokens? This action cannot be undone, and any applications using these tokens will no longer be able to authenticate.`,
  },
});
