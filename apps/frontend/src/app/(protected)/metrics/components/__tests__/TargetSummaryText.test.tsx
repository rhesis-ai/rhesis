import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import TargetSummaryText, {
  summaryParts,
  summaryPlainText,
} from '../TargetSummaryText';

describe('summaryParts', () => {
  it('sets the names in backticks apart as code', () => {
    expect(
      summaryParts('each tool call named `issue_refund` inside `billing_agent`')
    ).toEqual([
      { text: 'each tool call named ', code: false },
      { text: 'issue_refund', code: true },
      { text: ' inside ', code: false },
      { text: 'billing_agent', code: true },
    ]);
  });

  it('keeps an unclosed backtick as text', () => {
    expect(summaryParts('a `b')).toEqual([
      { text: 'a ', code: false },
      { text: '`b', code: false },
    ]);
  });

  it('reads a summary without names as one part', () => {
    expect(summaryParts('the whole run')).toEqual([
      { text: 'the whole run', code: false },
    ]);
  });
});

describe('TargetSummaryText', () => {
  it('renders names as code and keeps the sentence readable', () => {
    const { container } = render(
      <p>
        <TargetSummaryText summary="each span where `app.tier` is `gold`" />
      </p>
    );
    expect(container).toHaveTextContent('each span where app.tier is gold');
    expect(
      Array.from(container.querySelectorAll('code')).map(c => c.textContent)
    ).toEqual(['app.tier', 'gold']);
  });

  it('gives a plain form for labels', () => {
    expect(summaryPlainText('named `x`')).toBe('named x');
  });
});
