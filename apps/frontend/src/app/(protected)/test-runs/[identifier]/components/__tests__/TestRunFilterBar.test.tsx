import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import TestRunFilterBar, {
  type FilterState,
  type StatusFilter,
} from '../TestRunFilterBar';

function makeFilter(statusFilter: StatusFilter = 'all'): FilterState {
  return {
    searchQuery: '',
    statusFilter,
    selectedRequirements: [],
    overruleFilter: 'all',
    metricFilters: {},
    commentFilter: 'all',
    commentCountRange: { min: 0, max: 0 },
    taskFilter: 'all',
    taskCountRange: { min: 0, max: 0 },
  };
}

function renderBar(
  props: { statusFilter?: StatusFilter; hasInconclusive?: boolean } = {}
) {
  const onFilterChange = jest.fn();
  render(
    <TestRunFilterBar
      filter={makeFilter(props.statusFilter)}
      onFilterChange={onFilterChange}
      availableRequirements={[]}
      availableMetrics={[]}
      onDownload={jest.fn()}
      onCompare={jest.fn()}
      totalTests={0}
      filteredTests={0}
      variant="linkedEntities"
      hideViewModeToggle
      hasInconclusive={props.hasInconclusive}
    />
  );
  return onFilterChange;
}

describe('TestRunFilterBar status filter', () => {
  it('hides Inconclusive when the run has none', () => {
    renderBar();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.queryByText('Inconclusive')).not.toBeInTheDocument();
  });

  it('offers Inconclusive when the run has some', () => {
    const onFilterChange = renderBar({ hasInconclusive: true });
    fireEvent.click(screen.getByText('Inconclusive'));
    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ statusFilter: 'inconclusive' })
    );
  });

  it('keeps Inconclusive while it is the active filter', () => {
    renderBar({ statusFilter: 'inconclusive', hasInconclusive: false });
    expect(screen.getByText('Inconclusive')).toBeInTheDocument();
  });
});
