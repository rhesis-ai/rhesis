import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import TestRunReviewsTab from '../TestRunReviewsTab';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

function review(
  id: string,
  name: string,
  updatedAt: string,
  status = 'Pass',
  comments = ''
) {
  return {
    review_id: id,
    status: { name: status },
    user: { user_id: `user-${name}`, name },
    comments,
    created_at: updatedAt,
    updated_at: updatedAt,
    target: { type: 'test_result', reference: null },
  };
}

function result(
  id: string,
  reviews: ReturnType<typeof review>[]
): TestResultDetail {
  return {
    id,
    test_reviews: { reviews },
    test: { prompt: { content: `Prompt for ${id}` } },
  } as unknown as TestResultDetail;
}

describe('TestRunReviewsTab', () => {
  it('shows the empty state when no test in the run has been reviewed', () => {
    render(<TestRunReviewsTab testResults={[result('a', [])]} />);

    expect(screen.getByText('No reviews yet')).toBeInTheDocument();
  });

  it('flattens reviews from every test result into one list', () => {
    render(
      <TestRunReviewsTab
        testResults={[
          result('a', [review('r1', 'Alice', '2026-09-01T10:00:00Z')]),
          result('b', [review('r2', 'Bob', '2026-09-02T10:00:00Z')]),
        ]}
      />
    );

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('puts the most recently updated review first', () => {
    render(
      <TestRunReviewsTab
        testResults={[
          result('a', [review('r1', 'Older', '2026-09-01T10:00:00Z')]),
          result('b', [review('r2', 'Newer', '2026-09-05T10:00:00Z')]),
        ]}
      />
    );

    const names = screen
      .getAllByText(/Older|Newer/)
      .map(node => node.textContent);
    expect(names[0]).toBe('Newer');
  });

  it('hands back the result id so the caller can open it in place', () => {
    // The caller opens a drawer without leaving the Reviews tab, the way the
    // playground opens a trace from a conversation.
    const onViewTestResult = jest.fn();
    render(
      <TestRunReviewsTab
        testResults={[
          result('abc', [review('r1', 'Alice', '2026-09-01T10:00:00Z')]),
        ]}
        onViewTestResult={onViewTestResult}
      />
    );

    fireEvent.click(screen.getByText('Alice'));

    expect(onViewTestResult).toHaveBeenCalledWith('abc');
  });

  it('does not blow up when no handler is given', () => {
    render(
      <TestRunReviewsTab
        testResults={[
          result('abc', [review('r1', 'Alice', '2026-09-01T10:00:00Z')]),
        ]}
      />
    );

    fireEvent.click(screen.getByText('Alice'));

    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('shows the review comment and its verdict', () => {
    render(
      <TestRunReviewsTab
        testResults={[
          result('a', [
            review(
              'r1',
              'Alice',
              '2026-09-01T10:00:00Z',
              'Fail',
              'Wrong refusal'
            ),
          ]),
        ]}
      />
    );

    expect(screen.getByText('Wrong refusal')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});
