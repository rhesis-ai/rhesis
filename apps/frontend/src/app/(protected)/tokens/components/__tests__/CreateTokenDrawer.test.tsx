import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import CreateTokenDrawer from '../CreateTokenDrawer';

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({
    activeProject: { id: 'proj-1', name: 'My Project' },
    projects: [],
    loading: false,
    setActiveProject: jest.fn(),
    refresh: jest.fn(),
  }),
}));

const onClose = jest.fn();
const onCreateToken = jest.fn();

function renderDrawer(open = true) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <CreateTokenDrawer
        open={open}
        onClose={onClose}
        onCreateToken={onCreateToken}
      />
    </ThemeProvider>
  );
}

describe('CreateTokenDrawer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    onCreateToken.mockResolvedValue({ id: 'tok1', token: 'abc123' });
  });

  it('renders the drawer when open=true', () => {
    renderDrawer(true);
    expect(screen.getByText('Create New Token')).toBeInTheDocument();
  });

  it('does not show the drawer panel when open=false', () => {
    renderDrawer(false);
    const drawer = document.querySelector('.MuiDrawer-root');
    expect(drawer).not.toHaveClass('MuiModal-open');
  });

  it('renders the token name input', () => {
    renderDrawer();
    expect(screen.getByLabelText(/token name/i)).toBeInTheDocument();
  });

  it('renders the expiration select with a default value', () => {
    renderDrawer();
    expect(screen.getByText('30 days')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    renderDrawer();

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onCreateToken with name and 30 days when submitted', async () => {
    const user = userEvent.setup();
    renderDrawer();

    await user.type(screen.getByLabelText(/token name/i), 'My Token');
    await user.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onCreateToken).toHaveBeenCalledWith('My Token', 30);
    });
  });

  it('clears the name input when the drawer is opened again', async () => {
    const { rerender } = render(
      <ThemeProvider theme={lightTheme}>
        <CreateTokenDrawer
          open={false}
          onClose={onClose}
          onCreateToken={onCreateToken}
        />
      </ThemeProvider>
    );

    rerender(
      <ThemeProvider theme={lightTheme}>
        <CreateTokenDrawer
          open={true}
          onClose={onClose}
          onCreateToken={onCreateToken}
        />
      </ThemeProvider>
    );

    const nameInput = screen.getByLabelText(/token name/i) as HTMLInputElement;
    expect(nameInput.value).toBe('');
  });

  it('calls onCreateToken with null days when "never" is selected', async () => {
    const user = userEvent.setup();
    renderDrawer();

    await user.click(screen.getByText('30 days'));
    await user.click(screen.getByRole('option', { name: /never expire/i }));

    await user.type(screen.getByLabelText(/token name/i), 'Permanent Token');
    await user.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onCreateToken).toHaveBeenCalledWith('Permanent Token', null);
    });
  });
});
