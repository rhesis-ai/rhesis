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
        default: '#F2F9FD', // Light Background 1
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
      // Dark mode colors - adapted for Rhesis AI
      primary: {
        main: '#50B9E0',
        light: '#97D5EE',
        dark: '#2AA1CE',
        contrastText: '#1A1A1A',
      },
      secondary: {
        main: '#FD6E12',
        light: '#FDD803',
        dark: '#3D3D3D',
        contrastText: '#FFFFFF',
      },
      background: {
        default: '#1A1A1A',
        paper: '#3D3D3D',
        light1: '#2A2A2A',
        light2: '#333333',
        light3: '#404040',
        light4: '#4D4D4D'
      },
      text: {
        primary: '#FFFFFF',
        secondary: '#E5E7EB',
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
      textTransform: 'none'
    },
    caption: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 300, // Light
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF'
    }
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#50B9E0' : '#1A1A1A', // Rhesis primary blue / dark black
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
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#1A1A1A',
            color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
          },
          '& .MuiSvgIcon-root': {
            color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
          },
          '& .MuiButtonBase-root.Mui-selected': {
            backgroundColor: mode === 'light' ? '#50B9E0' : '#50B9E0', // Rhesis primary blue
            '& .MuiSvgIcon-root': {
              color: '#FFFFFF',
            },
            '& .MuiTypography-root.MuiListItemText-primary': {
              color: '#FFFFFF',
            },
          },
          '& .MuiDivider-root': {
            margin: '16px 0',
            borderColor: mode === 'light' ? 'rgba(61, 61, 61, 0.12)' : 'rgba(255, 255, 255, 0.12)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#3D3D3D',
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
            color: mode === 'light' ? '#50B9E0' : '#97D5EE',
            '&:hover': {
              backgroundColor: mode === 'light' ? 'rgba(80, 185, 224, 0.04)' : 'rgba(151, 213, 238, 0.04)',
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
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#3D3D3D',
          borderRadius: 12,
          boxShadow: mode === 'light' 
            ? '0 2px 8px rgba(80, 185, 224, 0.08)' 
            : '0 2px 8px rgba(0, 0, 0, 0.24)',
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

// Create the theme instance
const theme = createTheme(getDesignTokens('light'));

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

export default theme;

// Export the getDesignTokens function to be used by the theme provider
export { getDesignTokens };
  