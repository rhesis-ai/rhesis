import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { MetricRow, metricCounts } from '../ComparisonView';
import type { MetricResult } from '@/utils/api-client/interfaces/test-results';

const notApplicable = {
  score: null,
  is_successful: null,
  not_applicable: true,
  reason: 'The test has no expected response.',
} as unknown as MetricResult;

describe('metricCounts', () => {
  it('leaves not applicable metrics out of passed and total', () => {
    const counts = metricCounts({
      Relevance: { is_successful: true } as MetricResult,
      Tone: { is_successful: false } as MetricResult,
      'Exact Match': notApplicable,
    });

    expect(counts).toEqual({ passed: 1, total: 2 });
  });

  it('counts nothing when there are no metrics', () => {
    expect(metricCounts(undefined)).toEqual({ passed: 0, total: 0 });
  });
});

describe('MetricRow', () => {
  it('shows a not applicable metric as such, with its reason', () => {
    render(
      <ThemeProvider theme={createTheme()}>
        <MetricRow metricName="Exact Match" result={notApplicable} />
      </ThemeProvider>
    );

    expect(screen.getByLabelText('Not applicable')).toBeInTheDocument();
    expect(
      screen.getByText('Not applicable: The test has no expected response.')
    ).toBeInTheDocument();
  });
});
