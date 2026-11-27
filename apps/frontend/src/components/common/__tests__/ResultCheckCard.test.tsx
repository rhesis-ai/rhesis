import React from 'react';
import { render, screen } from '@testing-library/react';
import ResultCheckCard from '../ResultCheckCard';
import type { ResultCheckGroup } from '@/utils/result-checks';

function group(notApplicable: boolean): ResultCheckGroup {
  return {
    key: 'metrics',
    title: 'Metrics',
    checks: [
      {
        key: 'Response Time',
        label: 'Response Time',
        passed: null,
        reason: 'The span has no timing.',
        relevantTurns: [],
        metric: 'Response Time',
        result: {
          score: null,
          is_successful: null,
          reason: 'The span has no timing.',
          ...(notApplicable ? { not_applicable: true } : {}),
        } as never,
      },
    ],
  };
}

describe('ResultCheckCard', () => {
  it('labels a check with nothing to judge as not applicable', () => {
    render(<ResultCheckCard group={group(true)} />);

    expect(screen.getByText('Not applicable')).toBeInTheDocument();
    expect(screen.getByLabelText('Not applicable')).toBeInTheDocument();
    expect(screen.queryByText('Not scored')).not.toBeInTheDocument();
  });

  it('labels a check that could not reach a verdict as not scored', () => {
    render(<ResultCheckCard group={group(false)} />);

    expect(screen.getByText('Not scored')).toBeInTheDocument();
  });
});
