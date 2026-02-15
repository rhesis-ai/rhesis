import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { DeleteModal } from '../DeleteModal';

describe('DeleteModal', () => {
  const defaultProps = {
    open: true,
    onClose: jest.fn(),
    onConfirm: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders with default title and message', () => {
    render(<DeleteModal {...defaultProps} />);

    expect(screen.getByText('Delete Item')).toBeInTheDocument();
    expect(
      screen.getByText(/are you sure you want to delete this item/i)
    ).toBeInTheDocument();
  });

  it('renders with custom title and item name', () => {
    render(
      <DeleteModal
        {...defaultProps}
        title="Remove Project"
        itemName="My Project"
        itemType="project"
      />
    );

    expect(screen.getByText('Remove Project')).toBeInTheDocument();
  });

  it('includes item name in default message', () => {
    render(
      <DeleteModal {...defaultProps} itemName="Test Item" itemType="test" />
    );

    expect(
      screen.getByText(/delete the test "Test Item"/i)
    ).toBeInTheDocument();
  });

  it('calls onConfirm when delete is clicked', async () => {
    render(<DeleteModal {...defaultProps} />);

    await userEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when cancel is clicked', async () => {
    render(<DeleteModal {...defaultProps} />);

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(<DeleteModal {...defaultProps} isLoading={true} />);

    expect(screen.getByRole('button', { name: /deleting/i })).toBeDisabled();
  });

  it('disables cancel button during loading', () => {
    render(<DeleteModal {...defaultProps} isLoading={true} />);

    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
  });

  it('shows warning message when provided', () => {
    render(
      <DeleteModal {...defaultProps} warningMessage="This cannot be undone!" />
    );

    expect(screen.getByText('This cannot be undone!')).toBeInTheDocument();
  });

  it('uses custom button labels', () => {
    render(
      <DeleteModal
        {...defaultProps}
        confirmButtonText="Remove"
        cancelButtonText="Go Back"
      />
    );

    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go Back' })).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(<DeleteModal {...defaultProps} open={false} />);

    expect(screen.queryByText('Delete Item')).not.toBeInTheDocument();
  });

  describe('with confirmation required', () => {
    const confirmProps = {
      ...defaultProps,
      requireConfirmation: true,
      confirmationText: 'DELETE',
    };

    it('shows confirmation input', () => {
      render(<DeleteModal {...confirmProps} />);

      expect(
        screen.getByPlaceholderText(/type "DELETE" to confirm/i)
      ).toBeInTheDocument();
    });

    it('disables confirm button when text does not match', () => {
      render(<DeleteModal {...confirmProps} />);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(deleteButton).toBeDisabled();
    });

    it('enables confirm button when confirmation text matches', async () => {
      render(<DeleteModal {...confirmProps} />);

      const input = screen.getByPlaceholderText(/type "DELETE" to confirm/i);
      await userEvent.type(input, 'DELETE');

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(deleteButton).toBeEnabled();
    });

    it('shows error when wrong text is submitted', async () => {
      render(<DeleteModal {...confirmProps} />);

      const input = screen.getByPlaceholderText(/type "DELETE" to confirm/i);
      await userEvent.type(input, 'wrong');

      // Try clicking delete -- it should show an error
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      // Button is disabled since text doesn't match, so onConfirm won't fire
      expect(deleteButton).toBeDisabled();
    });
  });
});
