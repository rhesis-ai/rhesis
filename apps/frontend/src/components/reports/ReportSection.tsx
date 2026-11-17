'use client';

import * as React from 'react';
import { SectionCard } from '@/components/common/SectionCard';

/** A section of a report: the detail-page card, so core and EE sections look alike. */
export default function ReportSectionBlock({
  title,
  subtitle,
  aside,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <SectionCard title={title} subtitle={subtitle} actions={aside}>
      {children}
    </SectionCard>
  );
}

/** Pass rate as the report prints it: one decimal, or a dash when nothing was judged. */
export function formatPassRate(rate?: number | null): string {
  return rate === null || rate === undefined ? '—' : `${rate.toFixed(1)}%`;
}

/** A change in percentage points, signed: "+2.5", "−4.0", "±0.0". */
export function formatDelta(delta?: number | null): string {
  if (delta === null || delta === undefined) return '—';
  if (Math.abs(delta) < 0.05) return '±0.0';
  return `${delta > 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)}`;
}
