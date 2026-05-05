import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import PlanDisplay, { countProgress, isPlanComplete } from '../PlanDisplay';

// Mock MarkdownContent
jest.mock('@/components/common/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => (
    <div data-testid="markdown-content">{content}</div>
  ),
}));

describe('PlanDisplay', () => {
  const planText = '## Test Plan\n- Safety tests\n- Accuracy tests';

  it('renders the "Current Plan" heading', () => {
    render(<PlanDisplay plan={planText} />);

    expect(screen.getByText('Current Plan')).toBeInTheDocument();
  });

  it('starts collapsed by default', () => {
    render(<PlanDisplay plan={planText} />);

    // ExpandMore icon indicates collapsed state
    expect(screen.getByTestId('ExpandMoreIcon')).toBeInTheDocument();
  });

  it('expands when header is clicked', () => {
    render(<PlanDisplay plan={planText} />);

    fireEvent.click(screen.getByText('Current Plan'));

    expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    // ExpandLess icon indicates expanded state
    expect(screen.getByTestId('ExpandLessIcon')).toBeInTheDocument();
  });

  it('collapses when header is clicked again', () => {
    render(<PlanDisplay plan={planText} />);

    // Expand
    fireEvent.click(screen.getByText('Current Plan'));
    expect(screen.getByTestId('ExpandLessIcon')).toBeInTheDocument();

    // Collapse
    fireEvent.click(screen.getByText('Current Plan'));
    expect(screen.getByTestId('ExpandMoreIcon')).toBeInTheDocument();
  });

  it('shows expand icon when collapsed', () => {
    render(<PlanDisplay plan={planText} />);

    expect(screen.getByTestId('ExpandMoreIcon')).toBeInTheDocument();
  });

  it('shows collapse icon when expanded', () => {
    render(<PlanDisplay plan={planText} />);

    fireEvent.click(screen.getByText('Current Plan'));

    expect(screen.getByTestId('ExpandLessIcon')).toBeInTheDocument();
  });

  it('shows the "Plan Complete" badge when every actionable item is checked', () => {
    const complete = '## Plan\n- [x] First\n- [x] Second';
    render(<PlanDisplay plan={complete} />);

    expect(screen.getByText('Plan Complete')).toBeInTheDocument();
    expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
  });
});

describe('countProgress', () => {
  it('counts only actionable checklist items', () => {
    const plan = [
      '## Plan',
      '- [x] First',
      '- [ ] Second',
      '- Plain bullet (no checkbox)',
      '- [x] Third',
    ].join('\n');

    expect(countProgress(plan)).toEqual({ done: 2, total: 3 });
  });

  it('skips items tagged as existing/reused', () => {
    const plan = [
      '## Plan',
      '- [x] First *(existing)*',
      '- [ ] Second',
      '- [x] Third',
    ].join('\n');

    // The existing one is skipped from both done and total counts.
    expect(countProgress(plan)).toEqual({ done: 1, total: 2 });
  });

  it('returns zeros when there are no checkbox items', () => {
    expect(countProgress('## Plan\nJust a description')).toEqual({
      done: 0,
      total: 0,
    });
  });
});

describe('isPlanComplete', () => {
  it('is true when every actionable item is checked', () => {
    expect(isPlanComplete('- [x] One\n- [x] Two')).toBe(true);
  });

  it('is false when at least one item is unchecked', () => {
    expect(isPlanComplete('- [x] One\n- [ ] Two')).toBe(false);
  });

  it('is false when the plan has no checkbox items at all', () => {
    expect(isPlanComplete('## Plan\nText only')).toBe(false);
  });

  it('is false when only existing/reused items appear', () => {
    // Existing items don't count toward "done" — there's no real
    // work to complete here, so the plan isn't "complete" in the
    // sense that triggers the completion badge.
    expect(isPlanComplete('- [x] First *(existing)*')).toBe(false);
  });
});
