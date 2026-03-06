import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import CreateTokenModal from '../CreateTokenModal';

const onClose = jest.fn();
const onCreateToken = jest.fn();

function renderModal(open = true) {
  return render(
    <CreateTokenModal
      open={open}
      onClose={onClose}
      onCreateToken={onCreateToken}
    />
  );
}

describe('CreateTokenModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    onCreateToken.mockResolvedValue({ id: 'tok1', token: 'abc123' });
  });

  it('renders the dialog when open=true', () => {
    renderModal(true);
    expect(screen.getByText('Create New Token')).toBeInTheDocument();
  });

  it('does not render the dialog when open=false', () => {
    renderModal(false);
    expect(screen.queryByText('Create New Token')).not.toBeInTheDocument();
  });

  it('renders the token name input', () => {
    renderModal();
    expect(screen.getByLabelText(/token name/i)).toBeInTheDocument();
  });

  it('renders the expiration select with a default value', () => {
    renderModal();
    // Default value is "30 days" - verify the selected option text is visible
    expect(screen.getByText('30 days')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onCreateToken with name and 30 days when submitted', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText(/token name/i), 'My Token');
    await user.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onCreateToken).toHaveBeenCalledWith('My Token', 30);
    });
  });

  it('clears the name input when the modal is opened again', async () => {
    const { rerender } = render(
      <CreateTokenModal
        open={false}
        onClose={onClose}
        onCreateToken={onCreateToken}
      />
    );

    rerender(
      <CreateTokenModal
        open={true}
        onClose={onClose}
        onCreateToken={onCreateToken}
      />
    );

    const nameInput = screen.getByLabelText(/token name/i) as HTMLInputElement;
    expect(nameInput.value).toBe('');
  });

  it('calls onCreateToken with null days when "never" is selected', async () => {
    const user = userEvent.setup();
    renderModal();

    // The MUI Select displays the current value as visible text; click it to open the dropdown
    await user.click(screen.getByText('30 days'));
    await user.click(screen.getByRole('option', { name: /never expire/i }));

    await user.type(screen.getByLabelText(/token name/i), 'Permanent Token');
    await user.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onCreateToken).toHaveBeenCalledWith('Permanent Token', null);
    });
  });
});
