import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BaseDrawer, { filterUniqueValidOptions } from '../BaseDrawer';
import '@testing-library/jest-dom';

describe('BaseDrawer', () => {
  const mockOnClose = jest.fn();
  const mockOnSave = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders with open state', () => {
    render(
      <BaseDrawer open={true} onClose={mockOnClose} title="Test Drawer">
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText('Test Drawer')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('renders without header when showHeader is false', () => {
    render(
      <BaseDrawer open={true} onClose={mockOnClose} showHeader={false}>
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.queryByText('Test Drawer')).not.toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('uses custom close button text when provided', () => {
    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        title="Test Drawer"
        closeButtonText="Close"
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText('Close')).toBeInTheDocument();
    expect(screen.queryByText('Cancel')).not.toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <BaseDrawer open={false} onClose={mockOnClose} title="Test Drawer">
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.queryByText('Test Drawer')).not.toBeVisible();
  });

  it('calls onClose when Cancel button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <BaseDrawer open={true} onClose={mockOnClose} title="Test Drawer">
        <div>Test Content</div>
      </BaseDrawer>
    );

    await user.click(screen.getByText('Cancel'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('renders Save button when onSave is provided', () => {
    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        title="Test Drawer"
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText('Save Changes')).toBeInTheDocument();
  });

  it('calls onSave when Save button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        title="Test Drawer"
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    await user.click(screen.getByText('Save Changes'));
    expect(mockOnSave).toHaveBeenCalledTimes(1);
  });

  it('does not render Save button when onSave is not provided', () => {
    render(
      <BaseDrawer open={true} onClose={mockOnClose} title="Test Drawer">
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();
  });

  it('disables buttons when loading', () => {
    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        title="Test Drawer"
        loading={true}
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText('Cancel')).toBeDisabled();
    expect(screen.getByText('Executing...')).toBeDisabled();
  });

  it('displays error message when error is provided', () => {
    const errorMessage = 'Something went wrong';

    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        title="Test Drawer"
        error={errorMessage}
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('uses custom save button text when provided', () => {
    render(
      <BaseDrawer
        open={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        title="Test Drawer"
        saveButtonText="Create"
      >
        <div>Test Content</div>
      </BaseDrawer>
    );

    expect(screen.getByText('Create')).toBeInTheDocument();
  });
});

describe('filterUniqueValidOptions', () => {
  interface MockOption {
    id: string | number;
    name: string;
  }

  it('filters out entries with empty names', () => {
    const options: MockOption[] = [
      { id: 1, name: 'Valid Option' },
      { id: 2, name: '' },
      { id: 3, name: '   ' }, // whitespace only
      { id: 4, name: 'Another Valid Option' },
    ];

    const result = filterUniqueValidOptions(options);

    expect(result).toHaveLength(2);
    expect(result[0].name).toBe('Valid Option');
    expect(result[1].name).toBe('Another Valid Option');
  });

  it('removes duplicate entries based on id and name', () => {
    const options: MockOption[] = [
      { id: 1, name: 'Option 1' },
      { id: 2, name: 'Option 2' },
      { id: 1, name: 'Option 1' }, // duplicate
      { id: 3, name: 'Option 3' },
      { id: 2, name: 'Option 2' }, // duplicate
    ];

    const result = filterUniqueValidOptions(options);

    expect(result).toHaveLength(3);
    expect(result.map(option => `${option.id}-${option.name}`)).toEqual([
      '1-Option 1',
      '2-Option 2',
      '3-Option 3',
    ]);
  });

  it('handles empty array', () => {
    const result = filterUniqueValidOptions([]);
    expect(result).toEqual([]);
  });

  it('handles array with only invalid entries', () => {
    const options: MockOption[] = [
      { id: 1, name: '' },
      { id: 2, name: '   ' },
    ];

    const result = filterUniqueValidOptions(options);
    expect(result).toEqual([]);
  });
});
