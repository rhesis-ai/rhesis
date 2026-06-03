import React from 'react';
// Import from /pure to avoid the moduleNameMapper loop (this file IS the
// @testing-library/react mapping). Cleanup is wired up manually below.
import {
  render as rtlRender,
  cleanup,
  RenderOptions,
  RenderResult,
} from '@testing-library/react/pure';
export * from '@testing-library/react/pure';

// Mirror what @testing-library/react's index.js does: run cleanup after each test.
if (typeof afterEach === 'function') {
  afterEach(() => {
    cleanup();
  });
}
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';

function AllProviders({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={lightTheme}>{children}</ThemeProvider>;
}

function render(
  ui: React.ReactElement,
  options: Omit<RenderOptions, 'wrapper'> & {
    wrapper?: RenderOptions['wrapper'];
  } = {}
): RenderResult {
  const { wrapper: Wrapper, ...rest } = options;
  const Combined = Wrapper
    ? ({ children }: { children: React.ReactNode }) => (
        <AllProviders>
          <Wrapper>{children}</Wrapper>
        </AllProviders>
      )
    : AllProviders;
  return rtlRender(ui, { wrapper: Combined, ...rest });
}

export { render };
