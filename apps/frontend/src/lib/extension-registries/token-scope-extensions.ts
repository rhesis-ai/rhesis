/**
 * Extension point for token scope selection.
 *
 * The CreateTokenDrawer renders this slot when RBAC is available,
 * allowing users to restrict a token's capabilities to a specific
 * role's permission set. Without registration the drawer creates
 * full-access tokens (community behaviour).
 *
 * EE registers the implementation from `ee/frontend/src/rbac/register.tsx`.
 */

import type { ComponentType } from 'react';

// ---------------------------------------------------------------------------
// Prop contract
// ---------------------------------------------------------------------------

export interface TokenScopeFieldProps {
  /** null = full access (no scope restriction). */
  value: string[] | null;
  onChange: (scopes: string[] | null) => void;
}

// ---------------------------------------------------------------------------
// Extension bundle
// ---------------------------------------------------------------------------

export interface TokenScopeExtensions {
  /** Renders a scope picker in the create-token drawer. */
  TokenScopeField?: ComponentType<TokenScopeFieldProps>;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

let _extensions: TokenScopeExtensions = {};

export function registerTokenScopeExtensions(ext: TokenScopeExtensions): void {
  _extensions = { ..._extensions, ...ext };
}

export function getTokenScopeExtensions(): Readonly<TokenScopeExtensions> {
  return _extensions;
}

export function resetTokenScopeExtensions(): void {
  _extensions = {};
}
