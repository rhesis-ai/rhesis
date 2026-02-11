import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SearchAndFilterBar from '../SearchAndFilterBar';

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
});
