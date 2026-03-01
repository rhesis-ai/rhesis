import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeleteButton } from '../DeleteButton';

describe('DeleteButton', () => {
  it('renders with default label "Delete"', () => {
    render(<DeleteButton />);
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('renders with custom label', () => {
    render(<DeleteButton label="Remove" />);
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument();
  });

  it('renders children when provided (overrides label)', () => {
    render(<DeleteButton>Permanently Delete</DeleteButton>);
    expect(screen.getByText('Permanently Delete')).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const handleClick = jest.fn();

    render(<DeleteButton onClick={handleClick} />);

    await user.click(screen.getByRole('button'));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<DeleteButton disabled />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('does not call onClick when disabled', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const handleClick = jest.fn();

    render(<DeleteButton disabled onClick={handleClick} />);

    await user.click(screen.getByRole('button'));

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('renders the delete icon by default', () => {
    const { container } = render(<DeleteButton />);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('hides the delete icon when showIcon is false', () => {
    const { container } = render(<DeleteButton showIcon={false} />);
    expect(container.querySelector('svg')).not.toBeInTheDocument();
  });
});
