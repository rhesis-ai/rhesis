import type { ComponentType } from 'react';
import type { SvgIconProps } from '@mui/material';
import type { WithPermittedActions } from '@/types/affordances';
import { can } from '@/utils/affordances';

/**
 * Declarative description of an action a user can take on an entity.
 *
 * Actions are data, not JSX: declare them once per entity type and let a generic
 * renderer (`EntityActionBar`) show the permitted ones. Components stop writing
 * `canEdit`/`canDelete` booleans and per-button wiring.
 *
 * Two independent gates, deliberately kept separate:
 * - `capability` — the **server-driven** permission gate. Absent ⇒ no permission
 *   required. When present and not granted, the action is *hidden* (a "no" the
 *   backend decided).
 * - `isEnabled` — an optional **local business rule** (e.g. "can't delete the
 *   last item"). When false the action is *shown but disabled* with
 *   `disabledReason`. This is a different "no" from a permission denial and must
 *   not be conflated with it.
 *
 * `isVisible` covers non-permission visibility (entity state, props), e.g. hide
 * "Create task" on entities that are themselves tasks.
 */
export interface EntityAction<T extends WithPermittedActions> {
  /** Stable id; also the React key. */
  id: string;
  /** Tooltip / menu label. */
  label: string;
  icon?: ComponentType<SvgIconProps>;
  /** Full capability required on the subject (server-driven). Omit if none. */
  capability?: string;
  /** Non-permission visibility (entity state / props). Hidden when false. */
  isVisible?: (subject: T) => boolean;
  /** Local business rule: shown but disabled when false. */
  isEnabled?: (subject: T) => boolean;
  /** Tooltip shown when disabled by `isEnabled`. */
  disabledReason?: string;
  onSelect: (subject: T) => void;
}

export interface ResolvedEntityAction<T extends WithPermittedActions> {
  action: EntityAction<T>;
  /** False ⇒ render disabled (business rule); permission denials are filtered out entirely. */
  enabled: boolean;
}

/**
 * Filter an action list down to what the caller may see for `subject`:
 * permission-gated (hidden if not granted) and visibility-gated (hidden if
 * `isVisible` is false), then annotated with the `isEnabled` business rule.
 * Pure — the single place capability→affordance binding happens.
 */
export function resolveEntityActions<T extends WithPermittedActions>(
  subject: T | null | undefined,
  actions: EntityAction<T>[]
): ResolvedEntityAction<T>[] {
  if (!subject) return [];
  return actions
    .filter(a => (a.capability ? can(subject, a.capability) : true))
    .filter(a => a.isVisible?.(subject) ?? true)
    .map(a => ({ action: a, enabled: a.isEnabled?.(subject) ?? true }));
}
