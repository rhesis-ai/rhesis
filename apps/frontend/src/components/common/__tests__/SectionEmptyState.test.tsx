import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import '@testing-library/jest-dom';
import SectionEmptyState from '../SectionEmptyState';
import { lightTheme } from '@/styles/theme';
import RouteIcon from '@mui/icons-material/Route';

function renderSectionEmptyState(
  props: React.ComponentProps<typeof SectionEmptyState>
) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <SectionEmptyState {...props} />
    </ThemeProvider>
  );
}

describe('SectionEmptyState', () => {
  it('renders bordered inset content without a nested paper card', () => {
    const { container } = renderSectionEmptyState({
      icon: RouteIcon,
      title: 'No trace metrics yet',
      description: 'Add metrics to evaluate traces automatically.',
    });

    expect(screen.getByText('No trace metrics yet')).toBeInTheDocument();
    expect(
      screen.getByText('Add metrics to evaluate traces automatically.')
    ).toBeInTheDocument();
    expect(container.querySelector('.MuiPaper-root')).not.toBeInTheDocument();
  });
});
