'use client';

import * as React from 'react';
import {
  getReportSections,
  type ReportSectionSlot,
} from '@/lib/extension-registries';
import type { ReportDetail } from '@/utils/api-client/interfaces/report';

/** Registered sections for one slot. A section bound to a backend key shows only when the report has it. */
export default function ReportSlot({
  slot,
  report,
}: {
  slot: ReportSectionSlot;
  report: ReportDetail;
}) {
  const sections = React.useMemo(
    () => getReportSections().filter(section => section.slot === slot),
    [slot]
  );
  return (
    <>
      {sections
        .filter(
          section =>
            !section.sectionKey || section.sectionKey in report.sections
        )
        .map(section => {
          const Section = section.component;
          return <Section key={section.id} report={report} />;
        })}
    </>
  );
}
