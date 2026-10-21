import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import TestResultHeader from '../TestResultHeader';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

const result = {
  id: u(1),
  test_id: u(2),
  execution: 'ok',
  verdict: 'fail',
  tags: [{ id: u(3), name: 'dosage' }],
  test: { id: u(2) },
  test_output: {
    test_configuration: { goal: 'Dosage questions get the redirect reply.' },
  },
  test_metrics: {
    execution_time: 1,
    metrics: {
      Refusal: {
        score: 1,
        reason: '',
        backend: 'rhesis',
        description: '',
        is_successful: false,
      },
    },
  },
} as unknown as TestResultDetail;

describe('TestResultHeader', () => {
  it('shows the verdict, checks, tags and a link to the test on one line', () => {
    render(
      <ThemeProvider theme={lightTheme}>
        <TestResultHeader test={result} />
      </ThemeProvider>
    );
    expect(screen.getByText('0 of 1 check passed')).toBeInTheDocument();
    expect(screen.getByText('dosage')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open test/i })).toHaveAttribute(
      'href',
      `/tests/${u(2)}`
    );
    // The test's text lives on the tabs it explains, not in the header.
    expect(
      screen.queryByText('Dosage questions get the redirect reply.')
    ).not.toBeInTheDocument();
  });
});
