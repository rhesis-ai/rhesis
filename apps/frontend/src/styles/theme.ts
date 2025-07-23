"use client";
import { createTheme, PaletteMode } from '@mui/material/styles';

// Define theme settings for both light and dark modes
const getDesignTokens = (mode: PaletteMode) => ({
  palette: {
    mode,
    ...(mode === 'light' ? {
      // Light mode - keeping original colors
      primary: {
        main: '#1D2939',
        light: '#1D2939',
        dark: '#1D2939',
        contrastText: '#fff',
      },
      secondary: {
        main: '#F38755',
        light: '#F38755',
        dark: '#F38755',
        contrastText: '#fff',
      }
    } : {
      // Dark mode colors
      primary: {
        main: '#ffffff',
        light: '#ffffff',
        dark: '#ffffff',
        contrastText: '#1D2939',
      },
      secondary: {
        main: '#F38755',
        light: '#F38755',
        dark: '#F38755',
        contrastText: '#1D2939',
      },
      background: {
        default: '#1D2939',
        paper: '#344054',
      },
      text: {
        primary: '#ffffff',
        secondary: '#E5E7EB',
      },
    }),
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#1D2939' : '#344054',
          '& .MuiSvgIcon-root': {
            color: '#ffffff',
          },
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        root: {
          '& .MuiPaper-root': {
            backgroundColor: mode === 'light' ? '#ffffff' : '#1D2939',
            color: mode === 'light' ? '#1D2939' : '#ffffff',
          },
          '& .MuiSvgIcon-root': {
            color: mode === 'light' ? '#1D2939' : '#ffffff',
          },
          '& .MuiButtonBase-root.Mui-selected': {
            backgroundColor: mode === 'light' ? '#1D2939' : '#4B5563',
            '& .MuiSvgIcon-root': {
              color: '#ffffff',
            },
            '& .MuiTypography-root.MuiListItemText-primary': {
              color: '#ffffff',
            },
          },
          '& .MuiDivider-root': {
            margin: '16px 0',
            borderColor: mode === 'light' ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.12)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#ffffff' : '#344054',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          // Fix text button colors in dark mode
          '&.MuiButton-textPrimary': {
            color: mode === 'dark' ? '#1D2939' : undefined,
            '&:hover': {
              color: mode === 'dark' ? '#1D2939' : undefined,
            },
            '& .MuiSvgIcon-root': {
              color: mode === 'dark' ? '#1D2939' : undefined,
            },
          },
        },
      },
    },

    
  },
  chartPalettes: {
    line: ['#1976d2', '#9c27b0', '#2e7d32', '#ed6c02'], // primary, secondary, success, warning
    pie: ['#42a5f5', '#1976d2', '#1565c0'], // primary light, main, dark
    status: ['#2e7d32', '#ed6c02', '#d32f2f'] // success, warning, error
  }
});

// Create the theme instance
const theme = createTheme(getDesignTokens('light'));

// Add chartPalettes to theme type
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
}

export default theme;

// Export the getDesignTokens function to be used by the theme provider
export { getDesignTokens };
  