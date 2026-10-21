import React, { useContext } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ThemeContextProvider, { ColorModeContext } from '../ThemeProvider';

// Helper consumer component
function ColorModeConsumer() {
  const { mode, toggleColorMode } = useContext(ColorModeContext);
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={toggleColorMode}>toggle</button>
    </div>
  );
}

describe('ThemeContextProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme-mode');
    jest.clearAllMocks();
  });

  it('renders children', () => {
    render(
      <ThemeContextProvider>
        <span data-testid="child">hello</span>
      </ThemeContextProvider>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('defaults to "light" mode', () => {
    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );
    expect(screen.getByTestId('mode')).toHaveTextContent('light');
  });

  it('keeps a mode the user picked', async () => {
    localStorage.setItem('theme-mode-explicit', '1');
    document.documentElement.setAttribute('data-theme-mode', 'dark');

    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    expect(screen.getByTestId('mode')).toHaveTextContent('dark');
  });

  it("follows the browser over a stored mode the user didn't pick", () => {
    document.documentElement.setAttribute('data-theme-mode', 'light');
    (window.matchMedia as jest.Mock).mockImplementationOnce(query => ({
      matches: true,
      media: query,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }));

    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    expect(screen.getByTestId('mode')).toHaveTextContent('dark');
  });

  it('toggles from light to dark when toggleColorMode is called', async () => {
    const user = userEvent.setup();
    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    expect(screen.getByTestId('mode')).toHaveTextContent('light');
    await user.click(screen.getByRole('button', { name: /toggle/i }));
    expect(screen.getByTestId('mode')).toHaveTextContent('dark');
  });

  it('toggles from dark back to light', async () => {
    const user = userEvent.setup();
    localStorage.setItem('theme-mode-explicit', '1');
    document.documentElement.setAttribute('data-theme-mode', 'dark');

    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    await user.click(screen.getByRole('button', { name: /toggle/i }));
    expect(screen.getByTestId('mode')).toHaveTextContent('light');
  });

  it('persists theme to localStorage when toggled', async () => {
    const user = userEvent.setup();
    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    await user.click(screen.getByRole('button', { name: /toggle/i }));
    expect(localStorage.getItem('theme-mode')).toBe('dark');
  });

  it('sets data-theme-mode attribute when toggled', async () => {
    const user = userEvent.setup();
    render(
      <ThemeContextProvider>
        <ColorModeConsumer />
      </ThemeContextProvider>
    );

    await user.click(screen.getByRole('button', { name: /toggle/i }));
    expect(document.documentElement.getAttribute('data-theme-mode')).toBe(
      'dark'
    );
  });
});
