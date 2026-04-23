import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import PlanDisplay from '../PlanDisplay';

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
});
