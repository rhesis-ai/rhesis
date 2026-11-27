import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import MetricCard from '../MetricCard';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';

const CHOICES: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
  {
    on: 'tool_call',
    label: 'Each tool call',
    description: '',
    per_span: true,
    span_kind: 'tool.invoke',
  },
];

describe('MetricCard target line', () => {
  it('reads as a sentence under the name and links to the spans it judges', () => {
    render(
      <MetricCard
        title="Correct refund arguments"
        description=""
        target={{ on: 'tool_call', name: 'issue_refund' }}
        targetChoices={CHOICES}
        metricId="metric-1"
      />
    );

    const subtitle = screen.getByTestId('entity-card-subtitle');
    expect(subtitle).toHaveTextContent('on each tool call named issue_refund');
    const link = screen.getByRole('link', {
      name: 'each tool call named issue_refund',
    });
    expect(link).toHaveAttribute(
      'href',
      '/traces?view=spans&span_type=tool.invoke&tool=issue_refund&from_metric=metric-1'
    );
    expect(screen.getByTestId('BuildIcon')).toBeInTheDocument();
  });

  it('opens the target, not the metric, when the link is clicked', () => {
    const onClick = jest.fn();
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        target={{ on: 'turn' }}
        targetChoices={CHOICES}
        onClick={onClick}
      />
    );

    fireEvent.click(screen.getByRole('link', { name: 'each turn' }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('draws no target line until the labels load', () => {
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        target={{ on: 'turn' }}
      />
    );

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('no longer shows the target among the facts', () => {
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        scoreType="numeric"
        target={{ on: 'turn' }}
        targetChoices={CHOICES}
      />
    );

    expect(screen.getByTestId('entity-card-facts')).toHaveTextContent(
      'Numeric'
    );
    expect(screen.getByTestId('entity-card-facts')).not.toHaveTextContent(
      'Each turn'
    );
  });
});
