'use client';

/**
 * Preflight quota gating for a single action, and the reactive 402 path that
 * backs it up.
 *
 * Every gated surface needs the same five things: read the resource's usage,
 * compare against `ceiling` (never `limit`), decide whether this reader may
 * be offered an upgrade, build the notice, and handle the 402 that arrives
 * anyway. Hand-rolling that per drawer is how the copy and the threshold
 * drift apart, so it lives here once.
 *
 * The preflight is not a replacement for the server-side gate: usage can
 * change between render and submit, so the backend stays authoritative and
 * this only gives the user the answer earlier.
 */

import { useCallback } from 'react';
import { useCan } from '@/components/common/Can';
import { QuotaNotice } from '@/components/common/QuotaNotice';
import { Capability } from '@/constants/capabilities';
import type { QuotaResource } from '@/constants/quota';
import { useResourceUsage, useUsage } from '@/contexts/UsageContext';
import {
  isKnownQuotaResource,
  isUnlicensedPlan,
  parseQuotaError,
  quotaCopy,
} from '@/utils/quota';

/** Sentence and recourse joined for a surface that can only show a string
 * (a toast). No link: a snackbar auto-dismisses, so a link in one is a trap. */
function joinForToast(sentence: string, recourse: string): string {
  return recourse ? `${sentence} ${recourse}` : sentence;
}

export interface QuotaGate {
  /**
   * True when the backend would refuse this action right now. `false` while
   * usage is still loading, so the gate fails open and the 402 catches it --
   * blocking on unknown usage would disable the button for everyone during
   * the first round trip.
   */
  exhausted: boolean;
  /** Rendered notice for `BaseDrawer`'s `error` slot, or `undefined` when
   * the action is allowed. */
  notice: React.ReactNode | undefined;
  /** The same thing as a plain string, for a toast-only surface. */
  message: string | undefined;
}

/**
 * Gate one action on one resource.
 *
 * @param resource the metered resource this action consumes.
 * @param amount how much of it a single submit consumes. Defaults to 1;
 *   pass the real count where one submit consumes several (inviting five
 *   people at once consumes five seats), or the gate lets through a submit
 *   the backend will refuse partway.
 */
export function useQuotaGate(
  resource: QuotaResource,
  amount: number = 1
): QuotaGate {
  const usage = useResourceUsage(resource);
  const canUpgrade = useCanUpgrade();

  // Against `ceiling`, not `limit`: on a soft tier those differ by the
  // overage tolerance, and gating on `limit` would disable the action for an
  // org the backend would still accept, erasing the grace band its tier
  // grants.
  const exhausted =
    usage !== null &&
    usage.ceiling !== null &&
    usage.used + amount > usage.ceiling;

  if (!exhausted || usage === null) {
    return { exhausted: false, notice: undefined, message: undefined };
  }

  const copyInput = {
    resource,
    kind: usage.kind,
    used: usage.used,
    limit: usage.limit ?? 0,
    zone: 'blocked' as const,
    periodEnd: usage.period_end,
    canUpgrade,
  };
  const { sentence, recourse } = quotaCopy(copyInput);

  return {
    exhausted: true,
    notice: <QuotaNotice {...copyInput} />,
    message: joinForToast(sentence, recourse),
  };
}

/**
 * The string form of {@link useQuotaGate}, for an action whose cost is only
 * known at submit time. Returns the blocking message, or `null` when this
 * many units still fit.
 *
 * Inviting five people at once consumes five seats, so a fixed
 * `useQuotaGate(SEATS)` would wave through a submit the backend refuses
 * partway. Callers that know their cost at render should use
 * `useQuotaGate(resource, amount)` instead and disable the submit.
 */
export function useQuotaMessageFor(
  resource: QuotaResource
): (amount: number) => string | null {
  const usage = useResourceUsage(resource);
  const canUpgrade = useCanUpgrade();

  return useCallback(
    (amount: number) => {
      if (usage === null || usage.ceiling === null) return null;
      if (usage.used + amount <= usage.ceiling) return null;
      const { sentence, recourse } = quotaCopy({
        resource,
        kind: usage.kind,
        used: usage.used,
        limit: usage.limit ?? 0,
        zone: 'blocked',
        periodEnd: usage.period_end,
        canUpgrade,
      });
      return joinForToast(sentence, recourse);
    },
    [resource, usage, canUpgrade]
  );
}

/** Whether this reader can act on an upgrade: someone who can manage the org
 * (the same owner/admin gate as Org Settings) whose org has no active paid
 * license. Deliberately not `usage:read`, which every member holds.
 *
 * Gates on licence status rather than the edition name so a lapsed paid org --
 * held to community limits but still reporting its old edition -- is offered
 * the upgrade too. See `isUnlicensedPlan`. */
export function useCanUpgrade(): boolean {
  const canManageOrg = useCan(Capability.Organization.UPDATE);
  const { edition, licensed } = useUsage();
  return canManageOrg && isUnlicensedPlan(edition, licensed);
}

export interface QuotaErrorResult {
  notice: React.ReactNode;
  message: string;
}

/**
 * Turns a caught error into quota copy when it is a quota 402, or `null`
 * when it is anything else, so a call site reads:
 *
 *     const quota = asQuotaError(err);
 *     setError(quota?.notice ?? getApiErrorMessage(err, 'Failed to save'));
 *
 * The backup to every preflight: usage can change between render and submit,
 * and a member who reaches an action the preflight hid still gets a real
 * explanation rather than a raw error string.
 */
export function useQuotaErrorHandler(): (
  err: unknown
) => QuotaErrorResult | null {
  const canUpgrade = useCanUpgrade();

  return useCallback(
    (err: unknown) => {
      const quotaError = parseQuotaError(err);
      if (!quotaError || !isKnownQuotaResource(quotaError.resource))
        return null;

      const copyInput = {
        resource: quotaError.resource,
        kind: quotaError.kind,
        used: quotaError.used,
        limit: quotaError.limit ?? 0,
        zone: 'blocked' as const,
        periodEnd: quotaError.periodEnd,
        canUpgrade,
      };
      const { sentence, recourse } = quotaCopy(copyInput);
      return {
        notice: <QuotaNotice {...copyInput} />,
        message: joinForToast(sentence, recourse),
      };
    },
    [canUpgrade]
  );
}
