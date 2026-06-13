import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import '@testing-library/jest-dom';
import EntityEmptyState from '../EntityEmptyState';
import { lightTheme } from '@/styles/theme';
import RouteIcon from '@mui/icons-material/Route';

function renderEmptyState(
  props: React.ComponentProps<typeof EntityEmptyState>
) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <EntityEmptyState {...props} />
    </ThemeProvider>
  );
}

describe('EntityEmptyState', () => {
  it('renders card variant with Figma-aligned structure', () => {
    renderEmptyState({
      card: true,
      icon: RouteIcon,
      title: 'No task created yet',
      description: 'Lorem ipsum dolor sit amet.',
      actionLabel: 'Create task',
      onAction: jest.fn(),
    });

    expect(screen.getByText('No task created yet')).toBeInTheDocument();
    expect(screen.getByText('Lorem ipsum dolor sit amet.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create task/i })
    ).toBeInTheDocument();
  });

  it('calls onAction when the card CTA is clicked', async () => {
    const user = userEvent.setup();
    const onAction = jest.fn();

    renderEmptyState({
      card: true,
      icon: RouteIcon,
      title: 'No items yet',
      actionLabel: 'Add item',
      onAction,
    });

    await user.click(screen.getByRole('button', { name: /add item/i }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('omits the action button when actionLabel is not provided', () => {
    renderEmptyState({
      card: true,
      icon: RouteIcon,
      title: 'No trace metrics yet',
      description: 'Add metrics from the section header.',
    });

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
