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
