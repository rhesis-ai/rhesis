import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import TestResultHeader from '../TestResultHeader';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

const scored = {
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

function renderHeader(test: TestResultDetail) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <TestResultHeader test={test} />
    </ThemeProvider>
  );
}

describe('TestResultHeader', () => {
  it('shows nothing for a scored result: no verdict bar, no tags, no link', () => {
    const { container } = renderHeader(scored);
    expect(container).toBeEmptyDOMElement();
  });
});
