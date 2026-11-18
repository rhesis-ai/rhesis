import { render, screen } from '@testing-library/react';
import { Button } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { hexToRgb } from '@mui/system/colorManipulator';
import { getDesignTokens } from '@/styles/theme';
import { getAuthTokens } from '../authTokens';
import { useAuthStyles } from '../useAuthStyles';

jest.mock('@/contexts/NavigationItemsContext', () => ({
  useNavigationItems: () => ({ branding: undefined }),
}));

/** A navy that the app theme would paint near-invisible on the dark sign-in page. */
const NAVY = '#0B1E4D';

function AuthButtons() {
  const { primaryButton, outlinedButton } = useAuthStyles();
  return (
    <>
      <Button variant="contained" sx={primaryButton}>
        Continue with email
      </Button>
      <Button variant="outlined" sx={outlinedButton}>
        Continue with Google
      </Button>
    </>
  );
}

describe('useAuthStyles', () => {
  it('beats the theme button overrides on the sign-in page', () => {
    // The theme's `.MuiButton-containedPrimary` / `-outlinedPrimary` rules
    // used to win over these sx styles and paint the buttons in the app's
    // brand colours instead of the auth tokens.
    render(
      <ThemeProvider
        theme={createTheme(getDesignTokens('dark', { primary: NAVY }))}
      >
        <AuthButtons />
      </ThemeProvider>
    );
    const t = getAuthTokens('dark', NAVY);

    const email = screen.getByRole('button', { name: 'Continue with email' });
    expect(getComputedStyle(email).backgroundColor).toBe(hexToRgb(t.accent));

    const google = screen.getByRole('button', {
      name: 'Continue with Google',
    });
    expect(getComputedStyle(google).color).toBe('rgb(255, 255, 255)');
  });
});
