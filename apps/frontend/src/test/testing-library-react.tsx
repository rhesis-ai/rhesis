import React, { ReactElement, ReactNode } from 'react';
import {
  render as rtlRender,
  RenderOptions,
  RenderResult,
} from '@testing-library/react-original';
import { ThemeProvider } from '@mui/material/styles';
import { lightTheme } from '@/styles/theme';

export * from '@testing-library/react-original';

function ThemeWrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider theme={lightTheme}>{children}</ThemeProvider>;
}

function mergeWrappers(
  Outer: React.ComponentType<{ children: ReactNode }>,
  Inner?: React.ComponentType<{ children: ReactNode }>
) {
  if (!Inner) {
    return Outer;
  }
  return function MergedWrapper({ children }: { children: ReactNode }) {
    return (
      <Outer>
        <Inner>{children}</Inner>
      </Outer>
    );
  };
}

export function render(
  ui: ReactElement,
  options: RenderOptions = {}
): RenderResult {
  const { wrapper: userWrapper, ...rest } = options;
  return rtlRender(ui, {
    ...rest,
    wrapper: mergeWrappers(ThemeWrapper, userWrapper),
  });
}
