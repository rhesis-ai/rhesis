import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ActionBar from '../ActionBar';

describe('ActionBar', () => {
  it('renders nothing when neither button is provided', () => {
    const { container } = render(<ActionBar />);
    expect(container.querySelector('button')).not.toBeInTheDocument();
  });

  it('renders only the left button when rightButton is not provided', () => {
    render(<ActionBar leftButton={{ label: 'Cancel', onClick: jest.fn() }} />);
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });

  it('renders only the right button when leftButton is not provided', () => {
    render(<ActionBar rightButton={{ label: 'Save', onClick: jest.fn() }} />);
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });

  it('renders both buttons when both are provided', () => {
    render(
      <ActionBar
        leftButton={{ label: 'Back', onClick: jest.fn() }}
        rightButton={{ label: 'Next', onClick: jest.fn() }}
      />
    );
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('calls the left button onClick handler when clicked', async () => {
    const user = userEvent.setup();
    const handleLeft = jest.fn();
    render(<ActionBar leftButton={{ label: 'Cancel', onClick: handleLeft }} />);

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(handleLeft).toHaveBeenCalledTimes(1);
  });

  it('calls the right button onClick handler when clicked', async () => {
    const user = userEvent.setup();
    const handleRight = jest.fn();
    render(
      <ActionBar rightButton={{ label: 'Submit', onClick: handleRight }} />
    );

    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(handleRight).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when left button is disabled', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const handleLeft = jest.fn();
    render(
      <ActionBar
        leftButton={{ label: 'Cancel', onClick: handleLeft, disabled: true }}
      />
    );

    const button = screen.getByRole('button', { name: /cancel/i });
    expect(button).toBeDisabled();
    await user.click(button);

    expect(handleLeft).not.toHaveBeenCalled();
  });

  it('does not call onClick when right button is disabled', async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const handleRight = jest.fn();
    render(
      <ActionBar
        rightButton={{ label: 'Save', onClick: handleRight, disabled: true }}
      />
    );

    const button = screen.getByRole('button', { name: /save/i });
    expect(button).toBeDisabled();
    await user.click(button);

    expect(handleRight).not.toHaveBeenCalled();
  });

  it('defaults left button to outlined variant', () => {
    render(<ActionBar leftButton={{ label: 'Cancel', onClick: jest.fn() }} />);
    const button = screen.getByRole('button', { name: /cancel/i });
    expect(button).toHaveClass('MuiButton-outlined');
  });

  it('defaults right button to contained variant', () => {
    render(<ActionBar rightButton={{ label: 'Save', onClick: jest.fn() }} />);
    const button = screen.getByRole('button', { name: /save/i });
    expect(button).toHaveClass('MuiButton-contained');
  });

  it('applies custom variant to left button', () => {
    render(
      <ActionBar
        leftButton={{
          label: 'Action',
          onClick: jest.fn(),
          variant: 'contained',
        }}
      />
    );
    expect(screen.getByRole('button', { name: /action/i })).toHaveClass(
      'MuiButton-contained'
    );
  });

  it('applies custom variant to right button', () => {
    render(
      <ActionBar
        rightButton={{ label: 'Action', onClick: jest.fn(), variant: 'text' }}
      />
    );
    expect(screen.getByRole('button', { name: /action/i })).toHaveClass(
      'MuiButton-text'
    );
  });
});
