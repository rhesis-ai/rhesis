import { render, screen } from '@testing-library/react';
import { Button } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { blend, getContrastRatio } from '@mui/system/colorManipulator';
import { getDesignTokens } from '@/styles/theme';
import { getAuthTokens } from '../authTokens';
import { useAuthStyles } from '../useAuthStyles';

jest.mock('@/contexts/NavigationItemsContext', () => ({
  useNavigationItems: () => ({ branding: undefined }),
}));

/** A navy that used to vanish on the dark sign-in page. */
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

function renderAuthButtons(brand?: string) {
  render(
    <ThemeProvider
      theme={createTheme(
        getDesignTokens('dark', brand ? { primary: brand } : {})
      )}
    >
      <AuthButtons />
    </ThemeProvider>
  );
  return {
    email: getComputedStyle(
      screen.getByRole('button', { name: 'Continue with email' })
    ),
    google: getComputedStyle(
      screen.getByRole('button', { name: 'Continue with Google' })
    ),
  };
}

describe('useAuthStyles buttons', () => {
  it('keeps the standard sign-in buttons on the theme colours', () => {
    const { email, google } = renderAuthButtons();
    expect(email.backgroundColor).toBe('rgb(0, 128, 175)');
    expect(email.color).toBe('rgb(255, 255, 255)');
    expect(google.borderColor).toBe('rgb(51, 166, 203)');
    expect(google.color).toBe('rgb(51, 166, 203)');
  });

  it('keeps a dark brand colour visible, with a white label and outline', () => {
    const { email, google } = renderAuthButtons(NAVY);
    const t = getAuthTokens('dark', NAVY);
    const card = blend(t.ground, '#ffffff', 0.045);

    expect(
      getContrastRatio(email.backgroundColor, t.ground)
    ).toBeGreaterThanOrEqual(3);
    expect(email.color).toBe('rgb(255, 255, 255)');
    expect(getContrastRatio(google.borderColor, card)).toBeGreaterThanOrEqual(
      4.5
    );
    expect(getContrastRatio(google.color, card)).toBeGreaterThanOrEqual(4.5);
  });
});
