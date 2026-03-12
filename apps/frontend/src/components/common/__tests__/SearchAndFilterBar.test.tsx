import React, { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SearchAndFilterBar from '../SearchAndFilterBar';

function ControlledSearchBar(
  props: Omit<
    React.ComponentProps<typeof SearchAndFilterBar>,
    'searchValue' | 'onSearchChange'
  >
) {
  const [value, setValue] = useState('');
  return (
    <SearchAndFilterBar
      {...props}
      searchValue={value}
      onSearchChange={setValue}
    />
  );
}

describe('SearchAndFilterBar', () => {
  const defaultProps = {
    searchValue: '',
    onSearchChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders search input with default placeholder', () => {
    render(<SearchAndFilterBar {...defaultProps} />);

    expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
  });

  it('renders search input with custom placeholder', () => {
    render(
      <SearchAndFilterBar
        {...defaultProps}
        searchPlaceholder="Search tasks..."
      />
    );

    expect(screen.getByPlaceholderText('Search tasks...')).toBeInTheDocument();
  });

  it('displays the current search value', () => {
    render(<SearchAndFilterBar {...defaultProps} searchValue="hello" />);

    const input = screen.getByPlaceholderText('Search...');
    expect(input).toHaveValue('hello');
  });

  it('calls onSearchChange when typing', async () => {
    render(<SearchAndFilterBar {...defaultProps} />);

    const input = screen.getByPlaceholderText('Search...');
    await userEvent.type(input, 'test');

    // userEvent.type fires onChange for each character
    expect(defaultProps.onSearchChange).toHaveBeenCalled();
  });

  it('renders add button when onAddNew is provided', () => {
    const onAddNew = jest.fn();
    render(
      <SearchAndFilterBar
        {...defaultProps}
        onAddNew={onAddNew}
        addNewLabel="New Task"
      />
    );

    expect(
      screen.getByRole('button', { name: /new task/i })
    ).toBeInTheDocument();
  });

  it('does not render add button when onAddNew is not provided', () => {
    render(<SearchAndFilterBar {...defaultProps} />);

    expect(
      screen.queryByRole('button', { name: /new/i })
    ).not.toBeInTheDocument();
  });

  it('calls onAddNew when add button is clicked', async () => {
    const onAddNew = jest.fn();
    render(
      <SearchAndFilterBar
        {...defaultProps}
        onAddNew={onAddNew}
        addNewLabel="New Task"
      />
    );

    await userEvent.click(screen.getByRole('button', { name: /new task/i }));
    expect(onAddNew).toHaveBeenCalledTimes(1);
  });

  it('shows reset button when there are active filters', () => {
    const onReset = jest.fn();
    render(
      <SearchAndFilterBar
        {...defaultProps}
        hasActiveFilters={true}
        onReset={onReset}
      />
    );

    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('hides reset button when no active filters', () => {
    const onReset = jest.fn();
    render(
      <SearchAndFilterBar
        {...defaultProps}
        hasActiveFilters={false}
        onReset={onReset}
      />
    );

    expect(
      screen.queryByRole('button', { name: /reset/i })
    ).not.toBeInTheDocument();
  });

  it('calls onReset when reset button is clicked', async () => {
    const onReset = jest.fn();
    render(
      <SearchAndFilterBar
        {...defaultProps}
        hasActiveFilters={true}
        onReset={onReset}
      />
    );

    await userEvent.click(screen.getByRole('button', { name: /reset/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it('renders children as inline filters', () => {
    render(
      <SearchAndFilterBar {...defaultProps}>
        <div data-testid="custom-filter">Custom Filter</div>
      </SearchAndFilterBar>
    );

    expect(screen.getByTestId('custom-filter')).toBeInTheDocument();
  });

  describe('layout structure', () => {
    /**
     * Regression tests for the filter-overflow bug on the metrics page.
     *
     * When many backend filter chips are present (All, Custom, Garak, Rhesis,
     * Deepeval, Ragas) the ButtonGroup exceeded the inline children area, causing
     * the Filters badge button and the New Metric action button to collapse into a
     * floating card that overlapped the metric cards below.
     *
     * The fix moves children to their own dedicated row (`data-testid="filter-row"`),
     * separate from the search + action row (`data-testid="search-action-row"`).
     * Tests use those stable hooks rather than `parentElement` traversal so a future
     * internal DOM restructure does not silently break the assertions.
     */

    it('renders filter children inside the dedicated filter-row container', () => {
      render(
        <SearchAndFilterBar {...defaultProps}>
          <button data-testid="filter-chip">All</button>
        </SearchAndFilterBar>
      );

      const filterRow = screen.getByTestId('filter-row');
      expect(filterRow).toContainElement(screen.getByTestId('filter-chip'));
    });

    it('renders the action button inside search-action-row, not filter-row', () => {
      const onAddNew = jest.fn();
      render(
        <SearchAndFilterBar
          {...defaultProps}
          onAddNew={onAddNew}
          addNewLabel="New Metric"
        >
          <button data-testid="filter-chip">All</button>
        </SearchAndFilterBar>
      );

      const actionButton = screen.getByRole('button', { name: /new metric/i });
      const searchActionRow = screen.getByTestId('search-action-row');
      const filterRow = screen.getByTestId('filter-row');

      expect(searchActionRow).toContainElement(actionButton);
      expect(filterRow).not.toContainElement(actionButton);
    });

    it('renders filter children in filter-row, not in search-action-row', () => {
      const onAddNew = jest.fn();
      render(
        <SearchAndFilterBar
          {...defaultProps}
          onAddNew={onAddNew}
          addNewLabel="New Metric"
        >
          <button data-testid="filters-child">Filters</button>
        </SearchAndFilterBar>
      );

      const filtersChild = screen.getByTestId('filters-child');
      const searchActionRow = screen.getByTestId('search-action-row');
      const filterRow = screen.getByTestId('filter-row');

      expect(filterRow).toContainElement(filtersChild);
      expect(searchActionRow).not.toContainElement(filtersChild);
    });

    it('renders many filter chips in filter-row without leaking the action button into it', () => {
      // Simulates the exact metrics-page scenario: All + 5 backend tabs + Filters button
      const chips = ['All', 'Custom', 'Garak', 'Rhesis', 'Deepeval', 'Ragas'];
      const onAddNew = jest.fn();

      render(
        <SearchAndFilterBar
          {...defaultProps}
          onAddNew={onAddNew}
          addNewLabel="New Metric"
        >
          {chips.map(label => (
            <button key={label} data-testid={`chip-${label.toLowerCase()}`}>
              {label}
            </button>
          ))}
          <button data-testid="filters-child">Filters</button>
        </SearchAndFilterBar>
      );

      const filterRow = screen.getByTestId('filter-row');
      const actionButton = screen.getByRole('button', { name: /new metric/i });

      // Every chip and the Filters child must be inside filter-row
      chips.forEach(label =>
        expect(filterRow).toContainElement(
          screen.getByTestId(`chip-${label.toLowerCase()}`)
        )
      );
      expect(filterRow).toContainElement(screen.getByTestId('filters-child'));

      // The action button must NOT be inside filter-row
      expect(filterRow).not.toContainElement(actionButton);
    });

    it('does not render filter-row when no children are provided', () => {
      render(<SearchAndFilterBar {...defaultProps} />);

      expect(screen.queryByTestId('filter-row')).not.toBeInTheDocument();
    });
  });

  describe('focus retention while typing', () => {
    it('retains focus after each keystroke', async () => {
      render(<ControlledSearchBar />);
      const input = screen.getByPlaceholderText('Search...');

      await userEvent.click(input);
      for (const char of 'hello') {
        await userEvent.type(input, char);
        expect(input).toHaveFocus();
      }
    });

    it('accumulates full typed value without losing characters', async () => {
      render(<ControlledSearchBar />);
      const input = screen.getByPlaceholderText('Search...');

      await userEvent.click(input);
      await userEvent.type(input, 'hello world');

      expect(input).toHaveValue('hello world');
    });

    it('retains focus when filters are active alongside typing', async () => {
      const onReset = jest.fn();
      render(<ControlledSearchBar hasActiveFilters onReset={onReset} />);
      const input = screen.getByPlaceholderText('Search...');

      await userEvent.click(input);
      await userEvent.type(input, 'test query');

      expect(input).toHaveFocus();
      expect(input).toHaveValue('test query');
    });
  });
});
