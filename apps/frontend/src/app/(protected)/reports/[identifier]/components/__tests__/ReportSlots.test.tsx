import { render, screen } from '@testing-library/react';
import {
  registerReportRequirementColumn,
  registerReportSection,
  resetReportSections,
} from '@/lib/extension-registries';
import type { ReportDetail } from '@/utils/api-client/interfaces/report';
import ReportSlot from '../ReportSlot';
import ReportRequirementsTable from '../ReportRequirementsTable';

function report(sections: Record<string, unknown>): ReportDetail {
  return {
    id: 'r1',
    title: 'Release 2.4',
    endpoint_id: 'e1',
    status: 'draft',
    result_rule: 'latest',
    is_release: true,
    test_run_ids: [],
    tagged_run_ids: [],
    requirement_ids: [],
    sections,
    metrics: {
      result_rule: 'latest',
      versions_differ: false,
      runs: [],
      totals: {
        results: 2,
        passed: 1,
        failed: 1,
        inconclusive: 0,
        errored: 0,
        pass_rate: 50,
        requirements_tested: 1,
        requirements_total: 2,
        inconsistent: 0,
      },
      requirements: [
        {
          id: 'q1',
          name: 'No advice',
          level: 0,
          coverage: 'tested',
          tests: 2,
          passed: 1,
          failed: 1,
          errored: 0,
          pass_rate: 50,
          inconsistent: 0,
        },
        {
          id: 'q2',
          name: 'Plain language',
          level: 0,
          coverage: 'no_tests',
          tests: 0,
          passed: 0,
          failed: 0,
          errored: 0,
          pass_rate: null,
          inconsistent: 0,
        },
      ],
    },
  };
}

describe('report extension slots', () => {
  beforeEach(() => {
    resetReportSections();
    registerReportSection({
      id: 'by-impact',
      slot: 'after-summary',
      order: 10,
      sectionKey: 'by_impact',
      component: () => <p>By impact section</p>,
    });
    registerReportSection({
      id: 'trail',
      slot: 'details',
      order: 10,
      component: () => <p>Audit trail section</p>,
    });
    registerReportRequirementColumn({
      id: 'impact',
      order: 10,
      header: 'Impact',
      sectionKey: 'by_impact',
      cell: ({ row }) => <span>{`impact of ${row.name}`}</span>,
    });
  });

  it('shows a keyed section only when the backend sent its data', () => {
    const { rerender } = render(
      <ReportSlot slot="after-summary" report={report({})} />
    );
    expect(screen.queryByText('By impact section')).not.toBeInTheDocument();

    rerender(
      <ReportSlot slot="after-summary" report={report({ by_impact: {} })} />
    );
    expect(screen.getByText('By impact section')).toBeInTheDocument();
  });

  it('renders unkeyed sections in their own slot only', () => {
    render(<ReportSlot slot="details" report={report({})} />);
    expect(screen.getByText('Audit trail section')).toBeInTheDocument();
    expect(screen.queryByText('By impact section')).not.toBeInTheDocument();
  });

  it('adds the impact column only with by_impact data (Community has none)', () => {
    const { rerender } = render(
      <ReportRequirementsTable report={report({})} />
    );
    expect(screen.queryByText('Impact')).not.toBeInTheDocument();
    expect(screen.getByText('No tests yet')).toBeInTheDocument();

    rerender(<ReportRequirementsTable report={report({ by_impact: {} })} />);
    expect(screen.getByText('Impact')).toBeInTheDocument();
    expect(screen.getByText('impact of No advice')).toBeInTheDocument();
  });
});
