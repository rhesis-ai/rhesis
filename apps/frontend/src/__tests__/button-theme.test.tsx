import React from 'react';
import { render, screen } from '@testing-library/react';
import Button from '@mui/material/Button';
import lightTheme from '@/styles/theme';

const SX_COLOR = 'rgb(1, 2, 3)';

const cases = [
  ['contained', 'primary'],
  ['outlined', 'primary'],
  ['text', 'primary'],
  ['contained', 'secondary'],
  ['outlined', 'secondary'],
] as const;

describe('MuiButton theme colours do not outrank sx', () => {
  it.each(cases)('%s %s button keeps its sx colour', (variant, color) => {
    render(
      <Button variant={variant} color={color} sx={{ color: SX_COLOR }}>
        Action
      </Button>
    );
    expect(screen.getByRole('button', { name: 'Action' })).toHaveStyle({
      color: SX_COLOR,
    });
  });

  it('keeps button colour rules out of nested root selectors', () => {
    const root = lightTheme.components?.MuiButton?.styleOverrides
      ?.root as unknown as Record<string, unknown>;
    expect(root).not.toHaveProperty('&.MuiButton-containedPrimary');
    expect(root).not.toHaveProperty('&.MuiButton-containedSecondary');
    expect(root).not.toHaveProperty('&.MuiButton-outlinedPrimary');
    expect(root).not.toHaveProperty('&.MuiButton-outlinedSecondary');
    expect(root).not.toHaveProperty('&.MuiButton-textPrimary');
  });
});
