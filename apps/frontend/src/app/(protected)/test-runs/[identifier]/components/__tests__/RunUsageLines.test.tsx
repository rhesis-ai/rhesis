import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import RunUsageLines from '../RunUsageLines';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

function usage(
  overrides: Partial<TraceMetricsResponse> = {}
): TraceMetricsResponse {
  return {
    total_traces: 60,
    enriched_traces: 60,
    priced_traces: 60,
    total_spans: 180,
    total_tokens: 112557,
    total_input_tokens: 90000,
    total_output_tokens: 22557,
    total_cost_usd: 0.03,
    total_input_cost_usd: 0.02,
    total_output_cost_usd: 0.01,
    models_used: ['gemini-2.5-flash'],
    providers_used: ['gemini'],
    error_spans: 0,
    error_rate: 0,
    avg_duration_ms: 1,
    p50_duration_ms: 1,
    p95_duration_ms: 1,
    p99_duration_ms: 1,
    operation_breakdown: {},
    ...overrides,
  };
}

describe('RunUsageLines', () => {
  it('shows what the run spent, on how many tokens, with which model', () => {
    render(<RunUsageLines usage={usage()} />);

    expect(screen.getByText('$0.03')).toBeInTheDocument();
    expect(screen.getByText('112,557')).toBeInTheDocument();
    expect(screen.getByText('gemini/gemini-2.5-flash')).toBeInTheDocument();
  });

  it('renders nothing before the numbers arrive', () => {
    const { container } = render(<RunUsageLines usage={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for a run that traced nothing', () => {
    // Half a comparison invites the reader to infer the other half.
    const { container } = render(
      <RunUsageLines usage={usage({ total_traces: 0 })} />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('shows a dash rather than a zero nobody computed', () => {
    render(
      <RunUsageLines usage={usage({ priced_traces: 0, total_cost_usd: 0 })} />
    );

    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('shows $0.00 for a run that was priced and free', () => {
    render(<RunUsageLines usage={usage({ total_cost_usd: 0 })} />);

    expect(screen.getByText('$0.00')).toBeInTheDocument();
  });

  it('omits the model line when the run reported none', () => {
    render(
      <RunUsageLines usage={usage({ models_used: [], providers_used: [] })} />
    );

    expect(screen.queryByText('Model:')).not.toBeInTheDocument();
    expect(screen.getByText('112,557')).toBeInTheDocument();
  });

  describe('the cost delta', () => {
    it('reads as an improvement when the run got cheaper', () => {
      render(
        <RunUsageLines
          usage={usage({ total_cost_usd: 0.03 })}
          compareTo={usage({ total_cost_usd: 0.05 })}
        />
      );

      // Cheaper is better, so it is coloured the opposite way from pass rate.
      const delta = screen.getByText('(−$0.02)');
      expect(delta).toBeInTheDocument();
      expect(delta).toHaveStyle({ color: '#38ad87' });
    });

    it('reads as a regression when the run got more expensive', () => {
      render(
        <RunUsageLines
          usage={usage({ total_cost_usd: 0.09 })}
          compareTo={usage({ total_cost_usd: 0.05 })}
        />
      );

      expect(screen.getByText('(+$0.04)')).toBeInTheDocument();
    });

    it('says nothing when the two runs cost the same', () => {
      render(
        <RunUsageLines
          usage={usage({ total_cost_usd: 0.05 })}
          compareTo={usage({ total_cost_usd: 0.05 })}
        />
      );

      expect(screen.queryByText(/\(/)).not.toBeInTheDocument();
    });

    it('never compares against a cost nobody computed', () => {
      // A -100% against an unpriced baseline would be a fabricated saving.
      render(
        <RunUsageLines
          usage={usage({ total_cost_usd: 0.05 })}
          compareTo={usage({ priced_traces: 0, total_cost_usd: 0 })}
        />
      );

      expect(screen.getByText('$0.05')).toBeInTheDocument();
      expect(screen.queryByText(/\(/)).not.toBeInTheDocument();
    });

    it('shows no delta on the baseline side', () => {
      render(<RunUsageLines usage={usage({ total_cost_usd: 0.03 })} />);

      expect(screen.queryByText(/\(/)).not.toBeInTheDocument();
    });
  });
});
