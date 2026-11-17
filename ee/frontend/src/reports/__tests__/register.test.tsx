/**
 * EE report sections: registration, the licence gates (no teaser without them),
 * and the link from a report's audit trail to the filtered audit log.
 */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import {
  getReportRequirementColumns,
  getReportSections,
  resetReportSections,
} from '@/lib/extension-registries';
import type { ReportDetail } from '@/utils/api-client/interfaces/report';
import { registerReports } from '../register';
import { auditLogUrl } from '../components/AuditTrail';

const enabled = new Set<string>();
let canReadAuditLog = true;

jest.mock('@/contexts/FeaturesContext', () => ({
  FeatureGate: ({
    feature,
    fallback,
    children,
  }: {
    feature: string;
    fallback: React.ReactNode;
    children: React.ReactNode;
  }) => <>{enabled.has(feature) ? children : fallback}</>,
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => canReadAuditLog,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({
    href,
    children,
  }: {
    href: string;
    children: React.ReactNode;
  }) => <a href={href}>{children}</a>,
}));

const getAuditTrail = jest.fn();
jest.mock('../api', () => ({
  ReportAuditClient: jest.fn().mockImplementation(() => ({ getAuditTrail })),
}));

function report(overrides: Partial<ReportDetail> = {}): ReportDetail {
  return {
    id: 'r1',
    title: 'Release 2.4',
    endpoint_id: 'e1',
    status: 'published',
    result_rule: 'latest',
    is_release: true,
    test_run_ids: [],
    tagged_run_ids: [],
    requirement_ids: [],
    metrics: null,
    sections: {
      by_impact: {
        impacts: [
          {
            id: 'i1',
            name: 'Legal & compliance',
            requirements_tested: 2,
            requirements_total: 2,
            passed: 37,
            failed: 5,
            errored: 0,
            pass_rate: 88.1,
          },
        ],
        requirements: { q1: 'Legal & compliance' },
      },
      people: {
        author: { id: 'u1', name: 'Lena S.' },
        ran_tests: [{ id: 'u1', name: 'Lena S.' }],
        reviewers: [],
        verdicts_changed: 0,
      },
      stats: {
        results_judged: 3,
        results_errored: 1,
        response_time_ms: { mean: 1600, p95: 4100, measured: 3 },
      },
    },
    ...overrides,
  };
}

function renderSection(id: string, value: ReportDetail) {
  const section = getReportSections().find(s => s.id === id);
  if (!section) throw new Error(`${id} not registered`);
  const Section = section.component;
  return render(<Section report={value} />);
}

beforeEach(() => {
  resetReportSections();
  registerReports();
  enabled.clear();
  canReadAuditLog = true;
  getAuditTrail.mockReset();
});

describe('registerReports', () => {
  it('registers the sections and the impact column', () => {
    expect(getReportSections().map(s => s.id)).toEqual([
      'by-impact',
      'people',
      'audit-footer',
      'stats',
      'audit-trail',
    ]);
    expect(getReportRequirementColumns().map(c => c.id)).toEqual(['impact']);
  });

  it('is idempotent', () => {
    registerReports();
    expect(getReportSections()).toHaveLength(5);
  });
});

describe('advanced report sections', () => {
  it('render nothing without the feature: no teaser', () => {
    const { container } = renderSection('by-impact', report());
    expect(container).toBeEmptyDOMElement();
  });

  it('show by impact, people and stats with the feature', () => {
    enabled.add('advanced_reports');
    renderSection('by-impact', report());
    expect(screen.getByText('Legal & compliance')).toBeInTheDocument();
    expect(screen.getByText('88.1%')).toBeInTheDocument();

    renderSection('stats', report());
    expect(screen.getByText('1.6 s / 4.1 s')).toBeInTheDocument();
  });
});

describe('audit trail', () => {
  it('is hidden without the audit log, and never fetched', () => {
    const { container } = renderSection('audit-trail', report());
    expect(container).toBeEmptyDOMElement();
    expect(getAuditTrail).not.toHaveBeenCalled();
  });

  it('is left out for drafts', () => {
    enabled.add('audit_log');
    const { container } = renderSection(
      'audit-trail',
      report({ status: 'draft' })
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('lists entries and links to the filtered audit log', async () => {
    enabled.add('audit_log');
    getAuditTrail.mockResolvedValue([
      {
        id: 'a1',
        action: 'report.published',
        actor_label: 'Lena S.',
        occurred_at: '2026-10-27T14:02:00Z',
      },
    ]);
    renderSection('audit-trail', report());
    await waitFor(() =>
      expect(screen.getByText('Published by Lena S.')).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole('button', { name: 'Expand Audit trail' }));
    expect(
      screen.getByRole('link', { name: /open in audit log/i })
    ).toHaveAttribute('href', auditLogUrl('r1'));
  });

  it('hides the audit log link without audit_log:read', async () => {
    enabled.add('audit_log');
    canReadAuditLog = false;
    getAuditTrail.mockResolvedValue([]);
    renderSection('audit-trail', report());
    await waitFor(() =>
      expect(screen.getByText(/no audit entries/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
