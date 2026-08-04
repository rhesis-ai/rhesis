import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import InsightsSummaryBar from '../InsightsSummaryBar';

describe('InsightsSummaryBar', () => {
  it('shows test results wording', () => {
    render(
      <InsightsSummaryBar
        summary={{ total: 20, passed: 10, failed: 10, pass_rate: 50 }}
        endpointName="Insurance Chatbot"
      />
    );

    expect(screen.getByText(/50\.0%/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /\(10\/20 test results passed, 10\/20 failed\) · Insurance Chatbot/
      )
    ).toBeInTheDocument();
  });

  it('omits the failed clause when nothing failed', () => {
    render(
      <InsightsSummaryBar
        summary={{ total: 10, passed: 10, failed: 0, pass_rate: 100 }}
      />
    );

    expect(
      screen.getByText(/\(10\/10 test results passed\)/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/failed/)).not.toBeInTheDocument();
  });
});
