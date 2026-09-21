/**
 * Provider metadata served by `GET /tools/providers`.
 *
 * Mirrors `ProviderManifest.serialize()` in
 * `apps/backend/.../services/tool/providers/spec.py`. These facts used to be
 * duplicated as frontend constants and per-provider branches in the connection
 * drawer, which drifted from the backend whenever a provider changed.
 */

/** Where a field is persisted on the tool. */
export type ToolFieldStore = 'credentials' | 'metadata';

/**
 * How a connection obtains its credential.
 *
 * Only `api_token` exists today. The other two are named because the backend
 * contract already carries a `kind` discriminator, so a UI that branches on it
 * now needs no reshaping when they land.
 */
export type ToolAuthKind = 'api_token' | 'oauth2' | 'redirect_token';

export interface ToolAuthMethod {
  kind: ToolAuthKind;
  label: string;
  help_url: string;
  /**
   * Whether this deployment can actually offer the method. Always true for
   * `api_token`; an OAuth method is only available where the install has
   * client credentials configured, which is why this is resolved server-side
   * rather than assumed.
   */
  available: boolean;
}

export interface ToolProviderField {
  /** Dotted for nested metadata, e.g. `project.namespace`. */
  key: string;
  label: string;
  store: ToolFieldStore;
  required: boolean;
  secret: boolean;
  preserve_on_update: boolean;
  placeholder: string;
  help_text: string;
  help_url: string;
}

export interface ToolProvider {
  /** Matches the `ToolProviderType` lookup's `type_value`. */
  key: string;
  display_name: string;
  description: string;
  auth_methods: ToolAuthMethod[];
  fields: ToolProviderField[];
  /** Sorted action names, e.g. `['extract', 'test_connection']`. */
  actions: string[];
}
