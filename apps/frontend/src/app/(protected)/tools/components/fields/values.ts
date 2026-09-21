/**
 * Turning a saved tool into form values, and form values back into payloads.
 *
 * All of it is driven by `manifest.fields`, so the drawer no longer needs a
 * branch per provider. The parts that cannot be generic live in `adapters.ts`.
 */

import type { Tool } from '@/utils/api-client/interfaces/tool';
import type {
  ToolProvider,
  ToolProviderField,
} from '@/utils/api-client/interfaces/tool-provider';
import {
  CREDENTIAL_TRANSFORMS,
  METADATA_ADAPTERS,
  adapterKey,
} from './adapters';

/** Form state: one string per manifest field, keyed by `field.key`. */
export type FieldValues = Record<string, string>;

/**
 * Shown in place of a stored credential in edit mode.
 *
 * Credentials are encrypted and never returned by the API, so the form cannot
 * display them. Leaving this untouched means "keep what is stored", which the
 * backend honours for any field the manifest marks `preserve_on_update`.
 */
export const MASKED = '************';

export function isMasked(value: string): boolean {
  return value.trim() === MASKED;
}

function credentialFields(manifest: ToolProvider): ToolProviderField[] {
  return manifest.fields.filter(f => f.store === 'credentials');
}

function metadataFields(manifest: ToolProvider): ToolProviderField[] {
  return manifest.fields.filter(f => f.store === 'metadata');
}

/**
 * Fields an adapter folds into another one, so the form renders a single
 * input. GitHub's repo URL fills both `repository.owner` and `repository.repo`.
 */
function isSubsumed(manifest: ToolProvider, field: ToolProviderField): boolean {
  const adapter = METADATA_ADAPTERS[adapterKey(manifest.key, field.key)];
  if (adapter) return false;
  return metadataFields(manifest).some(other => {
    const otherAdapter = METADATA_ADAPTERS[adapterKey(manifest.key, other.key)];
    return (
      otherAdapter !== undefined &&
      other.key !== field.key &&
      field.key.startsWith(`${otherAdapter.storedKey}.`)
    );
  });
}

/** Fields the form actually renders, in manifest order. */
export function visibleFields(manifest: ToolProvider): ToolProviderField[] {
  return manifest.fields.filter(field => !isSubsumed(manifest, field));
}

function readMetadata(tool: Tool, field: ToolProviderField): string {
  const segments = field.key.split('.');
  let current: unknown = tool.tool_metadata;
  for (const segment of segments) {
    if (typeof current !== 'object' || current === null) return '';
    current = (current as Record<string, unknown>)[segment];
  }
  return typeof current === 'string' ? current : '';
}

/**
 * Form values for an existing tool.
 *
 * Credentials mask, metadata hydrates. That split is not a per-provider rule:
 * it falls straight out of `field.store`, because only metadata comes back
 * from the API.
 */
export function hydrateValues(manifest: ToolProvider, tool: Tool): FieldValues {
  const values: FieldValues = {};

  for (const field of credentialFields(manifest)) {
    values[field.key] = MASKED;
  }

  for (const field of metadataFields(manifest)) {
    const adapter = METADATA_ADAPTERS[adapterKey(manifest.key, field.key)];
    values[field.key] = adapter
      ? adapter.hydrate(tool)
      : readMetadata(tool, field);
  }

  return values;
}

/** Empty values for a new connection. */
export function emptyValues(manifest: ToolProvider): FieldValues {
  return Object.fromEntries(manifest.fields.map(f => [f.key, '']));
}

/**
 * Credentials to send.
 *
 * A masked or blank value is omitted rather than sent empty: omitting it lets
 * the backend keep the stored value for a `preserve_on_update` field, while
 * sending "" would read as a deliberate blank.
 */
export function buildCredentials(
  manifest: ToolProvider,
  values: FieldValues
): Record<string, string> {
  const credentials: Record<string, string> = {};

  for (const field of credentialFields(manifest)) {
    const raw = (values[field.key] ?? '').trim();
    if (!raw || isMasked(raw)) continue;
    const transform =
      CREDENTIAL_TRANSFORMS[adapterKey(manifest.key, field.key)];
    credentials[field.key] = transform ? transform(raw) : raw;
  }

  return credentials;
}

export interface MetadataResult {
  metadata: Record<string, unknown>;
  /** Set when an adapter could not parse what the user typed. */
  error?: string;
}

/**
 * Metadata to send.
 *
 * A blank optional field is left out entirely rather than sent empty, so a
 * cleared scope reads as "not set" rather than as an invalid value.
 */
export function buildMetadata(
  manifest: ToolProvider,
  values: FieldValues
): MetadataResult {
  const metadata: Record<string, unknown> = {};

  for (const field of metadataFields(manifest)) {
    const adapter = METADATA_ADAPTERS[adapterKey(manifest.key, field.key)];
    const raw = (values[field.key] ?? '').trim();

    if (adapter) {
      if (!raw) continue;
      const stored = adapter.toStored(raw);
      if (!stored) return { metadata, error: adapter.invalidMessage };
      Object.assign(metadata, stored);
      continue;
    }

    if (isSubsumed(manifest, field) || !raw) continue;

    const segments = field.key.split('.');
    let target = metadata;
    for (const segment of segments.slice(0, -1)) {
      const next = target[segment];
      target[segment] = typeof next === 'object' && next !== null ? next : {};
      target = target[segment] as Record<string, unknown>;
    }
    target[segments[segments.length - 1]] = raw;
  }

  return { metadata };
}

/**
 * Required fields the user has not filled in, as labels.
 *
 * A masked credential counts as filled: it means "keep what is stored".
 */
export function missingRequired(
  manifest: ToolProvider,
  values: FieldValues
): string[] {
  return visibleFields(manifest)
    .filter(field => {
      if (!field.required) return false;
      const raw = (values[field.key] ?? '').trim();
      return raw.length === 0;
    })
    .map(field => field.label);
}
