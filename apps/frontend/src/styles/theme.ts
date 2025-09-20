"use client";
import { createTheme, PaletteMode } from '@mui/material/styles';

// Define theme settings for both light and dark modes
const getDesignTokens = (mode: PaletteMode) => ({
  palette: {
    mode,
    ...(mode === 'light' ? {
      // Light mode - Rhesis AI colors
      primary: {
        main: '#50B9E0', // Primary Blue
        light: '#97D5EE', // Primary Light Blue
        dark: '#2AA1CE', // Primary CTA Blue
        contrastText: '#FFFFFF',
      },
      secondary: {
        main: '#FD6E12', // Secondary CTA Orange
        light: '#FDD803', // Accent Yellow
        dark: '#1A1A1A', // Dark Black
        contrastText: '#FFFFFF',
      },
      background: {
        default: '#FFFFFF', // White Background
        paper: '#FFFFFF', // White Background
        // Custom Rhesis AI background variants
        light1: '#F2F9FD',
        light2: '#E4F2FA',
        light3: '#C2E5F5',
        light4: '#97D5EE'
      },
      text: {
        primary: '#3D3D3D', // Dark Text
        secondary: '#1A1A1A', // Dark Black
      }
    } : {
      // Dark mode colors - Professional dark theme with Rhesis AI brand accents
      primary: {
        main: '#2AA1CE', // Primary CTA Blue
        light: '#3BC4F2', // Hover/active state for links & CTAs
        dark: '#2AA1CE', // Primary CTA Blue
        contrastText: '#FFFFFF',
      },
      secondary: {
        main: '#FD6E12', // Secondary CTA Orange
        light: '#F78166', // Warning/alert tone
        dark: '#58A6FF', // Info highlight
        contrastText: '#FFFFFF',
      },
      background: {
        default: '#0D1117', // Primary background (soft black)
        paper: '#161B22', // Secondary background/cards
        light1: '#0D1117', // Primary background
        light2: '#161B22', // Secondary background
        light3: '#1F242B', // Tertiary background/hover states
        light4: '#2C2C2C' // Subtle dividers/neutral contrast
      },
      text: {
        primary: '#E6EDF3', // Primary text (light gray, easy on eyes)
        secondary: '#A9B1BB', // Secondary text (subdued gray)
      },
    }),
  },
  typography: {
    fontFamily: '"Be Vietnam Pro", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    h2: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    h3: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    h4: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      fontSize: '1.75rem', // Smaller than default h4 (18px instead of ~24px)
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    h5: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    h6: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    body1: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    body2: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 300, // Light
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    },
    button: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      textTransform: 'none' as const
    },
    caption: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 300, // Light
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    }
  },
  components: {
    MuiSvgIcon: {
      styleOverrides: {
        root: {
          fontWeight: 200, // Extra light weight for all icons
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#50B9E0' : '#161B22', // Rhesis primary blue / secondary dark bg
          '& .MuiSvgIcon-root': {
            color: '#FFFFFF',
          },
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        root: {
          '& .MuiPaper-root': {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
            color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
          },
          '& .MuiSvgIcon-root': {
            color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
          },
          '& .MuiButtonBase-root.Mui-selected': {
            backgroundColor: mode === 'light' ? '#50B9E0' : '#2AA1CE', // Rhesis primary blue / primary CTA
            '& .MuiSvgIcon-root': {
              color: '#FFFFFF',
            },
            '& .MuiTypography-root.MuiListItemText-primary': {
              color: '#FFFFFF',
            },
          },
          '& .MuiDivider-root': {
            margin: '16px 0',
            borderColor: mode === 'light' ? 'rgba(61, 61, 61, 0.12)' : '#2C2C2C',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
          // Ensure consistent elevation shadows
          '&.MuiPaper-elevation1': {
            boxShadow: mode === 'light' 
              ? '0 2px 12px rgba(61, 61, 61, 0.15), 0 1px 4px rgba(61, 61, 61, 0.1)' 
              : '0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2)',
          },
          '&.MuiPaper-elevation2': {
            boxShadow: mode === 'light' 
              ? '0 4px 16px rgba(61, 61, 61, 0.18), 0 2px 6px rgba(61, 61, 61, 0.12)' 
              : '0 6px 20px rgba(0, 0, 0, 0.45), 0 3px 10px rgba(0, 0, 0, 0.25)',
          },
          '&.MuiPaper-elevation6': {
            boxShadow: mode === 'light' 
              ? '0 8px 24px rgba(61, 61, 61, 0.25), 0 4px 12px rgba(61, 61, 61, 0.15)' 
              : '0 12px 32px rgba(0, 0, 0, 0.6), 0 6px 16px rgba(0, 0, 0, 0.3)',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          fontFamily: '"Be Vietnam Pro", sans-serif',
          fontWeight: 600,
          // Primary button styling
          '&.MuiButton-containedPrimary': {
            backgroundColor: '#2AA1CE', // Primary CTA Blue
            color: '#FFFFFF',
            '&:hover': {
              backgroundColor: '#50B9E0', // Primary Blue on hover
            },
          },
          // Secondary button styling
          '&.MuiButton-containedSecondary': {
            backgroundColor: '#FD6E12', // Secondary CTA Orange
            color: '#FFFFFF',
            '&:hover': {
              backgroundColor: '#FDD803', // Accent Yellow on hover
              color: '#1A1A1A',
            },
          },
          // Text button styling
          '&.MuiButton-textPrimary': {
            color: mode === 'light' ? '#50B9E0' : '#3BC4F2',
            '&:hover': {
              backgroundColor: mode === 'light' ? 'rgba(80, 185, 224, 0.04)' : '#1F242B',
            },
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontFamily: '"Be Vietnam Pro", sans-serif',
          fontWeight: 500,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
          borderRadius: 12,
          boxShadow: mode === 'light' 
            ? '0 2px 12px rgba(61, 61, 61, 0.15), 0 1px 4px rgba(61, 61, 61, 0.1)' 
            : '0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2)',
        },
      },
    },
  },
  chartPalettes: {
    line: ['#50B9E0', '#FD6E12', '#2AA1CE', '#FDD803'], // Rhesis primary blue, orange, CTA blue, yellow
    pie: ['#97D5EE', '#50B9E0', '#2AA1CE'], // Rhesis light blue, primary blue, CTA blue
    status: ['#2AA1CE', '#FDD803', '#FD6E12'] // success (CTA blue), warning (yellow), error (orange)
  }
});

// Create theme instances for both modes
const lightTheme = createTheme(getDesignTokens('light'));
const darkTheme = createTheme(getDesignTokens('dark'));

// Add custom theme extensions
declare module '@mui/material/styles' {
  interface Theme {
    chartPalettes: {
      line: string[];
      pie: string[];
      status: string[];
    }
  }
  interface ThemeOptions {
    chartPalettes?: {
      line: string[];
      pie: string[];
      status: string[];
    }
  }
  interface TypeBackground {
    light1?: string;
    light2?: string;
    light3?: string;
    light4?: string;
  }
}

// Export light theme as default for backward compatibility
export default lightTheme;

// Export both theme instances and the getDesignTokens function
export { lightTheme, darkTheme, getDesignTokens };
  