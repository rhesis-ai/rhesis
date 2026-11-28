import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import MetricCard from '../MetricCard';
import type {
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';

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

function hrefTarget(href: string | null): unknown {
  const params = new URLSearchParams((href ?? '').split('?')[1] ?? '');
  return JSON.parse(params.get('target') ?? 'null');
}

describe('MetricCard target line', () => {
  it("reads the API's short summary under the name and links to exactly its spans", () => {
    const target: MetricTarget = { on: 'tool_call', name: 'issue_refund' };
    render(
      <MetricCard
        title="Correct refund arguments"
        description=""
        target={target}
        targetSummary="each tool call named `issue_refund`"
        targetChoices={CHOICES}
        metricId="metric-1"
      />
    );

    const subtitle = screen.getByTestId('entity-card-subtitle');
    expect(subtitle).toHaveTextContent('on each tool call named issue_refund');
    expect(subtitle.querySelector('code')).toHaveTextContent('issue_refund');
    const link = screen.getByRole('link', {
      name: 'each tool call named issue_refund',
    });
    const href = link.getAttribute('href');
    expect(href).toMatch(
      /^\/traces\?view=spans&target=.*&from_metric=metric-1$/
    );
    expect(hrefTarget(href)).toEqual(target);
    expect(screen.getByTestId('BuildIcon')).toBeInTheDocument();
  });

  it('opens the target, not the metric, when the link is clicked', () => {
    const onClick = jest.fn();
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        target={{ on: 'turn' }}
        targetSummary="each turn"
        targetChoices={CHOICES}
        onClick={onClick}
      />
    );

    fireEvent.click(screen.getByRole('link', { name: 'each turn' }));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('draws no target line without a summary', () => {
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        target={{ on: 'turn' }}
        targetChoices={CHOICES}
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
        targetSummary="each turn"
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

  it('puts the full summary in the tooltip when the short one counts conditions', async () => {
    render(
      <MetricCard
        title="Refund matches the order"
        description=""
        target={{
          on: 'span',
          where: [
            { field: 'kind', op: '==', value: 'tool.invoke' },
            { field: 'app.channel', op: '!=', value: 'internal' },
            { field: 'app.tier', op: '==', value: 'gold' },
          ],
        }}
        targetSummary="each tool call where `app.channel` is not `internal` and 1 more condition"
        targetSummaryFull="each tool call where `app.channel` is not `internal` and `app.tier` is `gold`"
        targetChoices={CHOICES}
      />
    );

    const link = screen.getByTestId('metric-target-link');
    expect(link).toHaveTextContent(
      'each tool call where app.channel is not internal and 1 more condition'
    );
    // A span target with a kind condition takes that kind's icon.
    expect(screen.getByTestId('BuildIcon')).toBeInTheDocument();
    fireEvent.mouseOver(link);
    expect(
      await screen.findByText(
        'Show the spans this metric judges: each tool call where app.channel is not internal and app.tier is gold'
      )
    ).toBeInTheDocument();
  });

  it('keeps the short tooltip when nothing is left out', async () => {
    render(
      <MetricCard
        title="Answer relevancy"
        description=""
        target={{ on: 'tool_call', within: 'billing_agent' }}
        targetSummary="each tool call inside `billing_agent`"
        targetSummaryFull="each tool call inside `billing_agent`"
        targetChoices={CHOICES}
      />
    );

    fireEvent.mouseOver(screen.getByTestId('metric-target-link'));
    expect(
      await screen.findByText('Show the spans this metric judges')
    ).toBeInTheDocument();
  });
});
