import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';

import RequirementMetricsViewer from '../RequirementMetricsViewer';
import type { RequirementListItem } from '@/utils/api-client/interfaces/requirement';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/hooks/useAccessibilityMode', () => ({
  useAccessibilityMode: () => false,
}));

jest.mock('@/hooks/useLookups', () => ({
  useMetricTargets: () => ({
    data: [
      {
        on: 'tool_call',
        label: 'Each tool call',
        description: '',
        per_span: true,
        span_kind: 'tool.invoke',
      },
    ],
  }),
}));

const REQUIREMENT = {
  id: 'requirement-1',
  name: 'Refunds are right',
  metrics: [
    {
      id: 'metric-1',
      name: 'Correct refund arguments',
      description: '',
      score_type: 'numeric',
      config: { target: { on: 'tool_call', name: 'issue_refund' } },
      backend_type: { id: 'bt', type_value: 'custom' },
      metric_type: { id: 'mt', type_value: 'custom-prompt' },
      target_summary: 'each tool call named `issue_refund`',
      target_summary_short: 'each tool call named `issue_refund`',
    },
  ],
} as unknown as RequirementListItem;

describe('RequirementMetricsViewer', () => {
  it("shows each metric's target line from the list's own summary", () => {
    render(
      <RequirementMetricsViewer
        open
        onClose={jest.fn()}
        requirement={REQUIREMENT}
        onRefresh={jest.fn()}
      />
    );

    const link = screen.getByTestId('metric-target-link');
    expect(link).toHaveTextContent('each tool call named issue_refund');
    expect(link.getAttribute('href')).toMatch(/^\/traces\?view=spans&target=/);
    expect(link.getAttribute('href')).toContain('from_metric=metric-1');
  });
});
