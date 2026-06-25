import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import InsightsSummaryBar from '../InsightsSummaryBar';

describe('InsightsSummaryBar', () => {
  it('shows test results wording and unique failed count when they differ', () => {
    render(
      <InsightsSummaryBar
        summary={{ total: 20, passed: 10, failed: 10, pass_rate: 50 }}
        endpointName="Insurance Chatbot"
        failedTestCaseCount={5}
      />
    );

    expect(screen.getByText(/50\.0%/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /\(10\/20 test results passed, 10 failed · 5 unique test cases failed\) · Insurance Chatbot/
      )
    ).toBeInTheDocument();
  });

  it('omits unique failed count when it matches execution failures', () => {
    render(
      <InsightsSummaryBar
        summary={{ total: 10, passed: 7, failed: 3, pass_rate: 70 }}
        failedTestCaseCount={3}
      />
    );

    expect(
      screen.getByText(/\(7\/10 test results passed, 3 failed\)/)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/unique test cases failed/)
    ).not.toBeInTheDocument();
  });
});
