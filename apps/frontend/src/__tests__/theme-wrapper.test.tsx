import React from 'react';
import { render, screen } from '@testing-library/react';
import { useTheme } from '@mui/material/styles';

function ThemeProbe() {
  const theme = useTheme();
  return (
    <div
      data-testid="probe"
      data-has-greyscale={String(Boolean(theme.palette.greyscale))}
      data-border={theme.palette.greyscale?.border ?? 'missing'}
    />
  );
}

describe('global test theme wrapper', () => {
  it('provides palette.greyscale from lightTheme', () => {
    render(<ThemeProbe />);
    expect(screen.getByTestId('probe')).toHaveAttribute(
      'data-has-greyscale',
      'true'
    );
  });
});
