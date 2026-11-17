/**
 * Shapes of the EE report sections, as built by
 * `ee/backend/src/rhesis/backend/ee/reports/sections.py`. They arrive inside
 * `report.sections` typed `unknown`, so each comes with a narrowing reader that
 * returns `undefined` for anything that doesn't fit.
 */

import type { ReportDetail } from '@/utils/api-client/interfaces/report';

export interface ImpactRow {
  id: string | null;
  name: string;
  requirements_tested: number;
  requirements_total: number;
  passed: number;
  failed: number;
  errored: number;
  pass_rate: number | null;
}

export interface ByImpactSection {
  impacts: ImpactRow[];
  /** Requirement id -> impact name, for every picked requirement. */
  requirements: Record<string, string>;
}

export interface ReportPerson {
  id: string;
  name: string;
}

export interface PeopleSection {
  author: ReportPerson | null;
  ran_tests: ReportPerson[];
  reviewers: ReportPerson[];
  verdicts_changed: number;
}

export interface StatsSection {
  results_judged: number;
  results_errored: number;
  response_time_ms: { mean: number; p95: number; measured: number } | null;
}

export interface ReportAuditEntry {
  id: string;
  action: string;
  actor_label?: string | null;
  occurred_at: string;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function byImpactOf(report: ReportDetail): ByImpactSection | undefined {
  const value = report.sections.by_impact;
  if (!isObject(value) || !Array.isArray(value.impacts)) return undefined;
  if (!isObject(value.requirements)) return undefined;
  return value as unknown as ByImpactSection;
}

export function peopleOf(report: ReportDetail): PeopleSection | undefined {
  const value = report.sections.people;
  if (!isObject(value) || !Array.isArray(value.ran_tests)) return undefined;
  return value as unknown as PeopleSection;
}

export function statsOf(report: ReportDetail): StatsSection | undefined {
  const value = report.sections.stats;
  if (!isObject(value) || typeof value.results_judged !== 'number') {
    return undefined;
  }
  return value as unknown as StatsSection;
}
