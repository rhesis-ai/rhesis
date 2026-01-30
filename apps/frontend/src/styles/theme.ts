'use client';
import { createTheme, PaletteMode } from '@mui/material/styles';

// Define theme settings for both light and dark modes
const getDesignTokens = (mode: PaletteMode) => ({
  palette: {
    mode,
    ...(mode === 'light'
      ? {
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
            light4: '#97D5EE',
          },
          text: {
            primary: '#3D3D3D', // Dark Text
            secondary: '#1A1A1A', // Dark Black
          },
          success: {
            main: '#2E7D32', // Material success green, dark enough for contrast
            contrastText: '#FFFFFF',
          },
          warning: {
            main: '#F57C00', // Amber 800, lighter than CTA orange
            contrastText: '#FFFFFF',
          },
          error: {
            main: '#C62828', // Strong error red, good contrast
            contrastText: '#FFFFFF',
          },
        }
      : {
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
            light4: '#2C2C2C', // Subtle dividers/neutral contrast
          },
          text: {
            primary: '#E6EDF3', // Primary text (light gray, easy on eyes)
            secondary: '#A9B1BB', // Secondary text (subdued gray)
          },
          success: {
            main: '#86EFAC', // Soft mint green, readable on dark backgrounds
            contrastText: '#000000',
          },
          warning: {
            main: '#FCD34D', // Warm amber yellow, readable on dark
            contrastText: '#000000',
          },
          error: {
            main: '#FCA5A5', // Soft red-pink, accessible on dark
            contrastText: '#000000',
          },
        }),
  },
  shape: {
    borderRadius: 4, // Default MUI border radius
    sharp: 0, // Sharp corners (no border radius)
    circular: '50%', // For circular elements
  },
  typography: {
    fontFamily: '"Be Vietnam Pro", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    h2: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    h3: {
      fontFamily: '"Sora", "Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    h4: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      fontSize: '1.75rem', // Smaller than default h4 (18px instead of ~24px)
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    h5: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    h6: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    body1: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    body2: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 300, // Light
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    button: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      textTransform: 'none' as const,
    },
    caption: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 300, // Light
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    subtitle1: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      fontSize: '1rem', // 16px
      lineHeight: 1.75,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    subtitle2: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 500, // Medium
      fontSize: '0.875rem', // 14px
      lineHeight: 1.57,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    overline: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 600, // Semibold
      fontSize: '0.75rem', // 12px
      lineHeight: 2.66,
      letterSpacing: '0.08333em',
      textTransform: 'uppercase' as const,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    // Custom typography variants for specific use cases
    chartLabel: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      fontSize: '0.75rem', // 12px - for chart labels
      lineHeight: 1.5,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    chartTick: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      fontSize: '0.625rem', // 10px - for chart ticks
      lineHeight: 1.4,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
    helperText: {
      fontFamily: '"Be Vietnam Pro", sans-serif',
      fontWeight: 400, // Regular
      fontSize: '0.875rem', // 14px - for loading/helper text
      lineHeight: 1.43,
      color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
    },
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
          backgroundColor: mode === 'light' ? '#2AA1CE' : '#161B22', // Rhesis primary CTA blue / secondary dark bg
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
            '& .MuiTypography-root.MuiTypography-caption': {
              color: '#FFFFFF',
            },
          },
          '& .MuiDivider-root': {
            margin: '16px 0',
            borderColor:
              mode === 'light' ? 'rgba(61, 61, 61, 0.12)' : '#2C2C2C',
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
            boxShadow:
              mode === 'light'
                ? '0 2px 12px rgba(61, 61, 61, 0.15), 0 1px 4px rgba(61, 61, 61, 0.1)'
                : '0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2)',
          },
          '&.MuiPaper-elevation2': {
            boxShadow:
              mode === 'light'
                ? '0 4px 16px rgba(61, 61, 61, 0.18), 0 2px 6px rgba(61, 61, 61, 0.12)'
                : '0 6px 20px rgba(0, 0, 0, 0.45), 0 3px 10px rgba(0, 0, 0, 0.25)',
          },
          '&.MuiPaper-elevation6': {
            boxShadow:
              mode === 'light'
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
          // Outlined button styling
          '&.MuiButton-outlinedPrimary': {
            color: '#2AA1CE', // Primary CTA Blue
            borderColor: '#2AA1CE',
            backgroundColor: 'transparent',
            '&:hover': {
              backgroundColor: '#2AA1CE', // Fill with CTA blue on hover
              color: '#FFFFFF',
              borderColor: '#2AA1CE',
            },
          },
          '&.MuiButton-outlinedSecondary': {
            color: '#FD6E12', // Secondary CTA Orange
            borderColor: '#FD6E12',
            backgroundColor: 'transparent',
            '&:hover': {
              backgroundColor: '#FD6E12', // Fill with orange on hover
              color: '#FFFFFF',
              borderColor: '#FD6E12',
            },
          },
          // Text button styling
          '&.MuiButton-textPrimary': {
            color: mode === 'light' ? '#50B9E0' : '#3BC4F2',
            '&:hover': {
              backgroundColor:
                mode === 'light' ? 'rgba(80, 185, 224, 0.04)' : '#1F242B',
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
        // Default chip styling - use neutral colors, not CTA colors
        colorDefault: {
          backgroundColor: mode === 'light' ? '#F5F5F5' : '#2C2C2C',
          color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
          '&.MuiChip-outlined': {
            borderColor: mode === 'light' ? '#E0E0E0' : '#404040',
            backgroundColor: 'transparent',
          },
        },
        // Info chips - use subtle blue (not CTA blue)
        colorInfo: {
          backgroundColor: mode === 'light' ? '#E4F2FA' : '#1F2937',
          color: mode === 'light' ? '#1565C0' : '#93C5FD',
          '&.MuiChip-outlined': {
            borderColor: mode === 'light' ? '#90CAF9' : '#3B82F6',
            backgroundColor: 'transparent',
          },
        },
        // Success chips - use notification success colors
        colorSuccess: {
          backgroundColor: mode === 'light' ? '#E8F5E8' : '#1F2937',
          color: mode === 'light' ? '#2E7D32' : '#86EFAC',
          '&.MuiChip-outlined': {
            borderColor: mode === 'light' ? '#2E7D32' : '#86EFAC',
            backgroundColor: 'transparent',
          },
        },
        // Warning chips - use notification warning colors
        colorWarning: {
          backgroundColor: mode === 'light' ? '#FFF8E1' : '#1F2937',
          color: mode === 'light' ? '#F57C00' : '#FCD34D',
          '&.MuiChip-outlined': {
            borderColor: mode === 'light' ? '#F57C00' : '#FCD34D',
            backgroundColor: 'transparent',
          },
        },
        // Error chips - use notification error colors
        colorError: {
          backgroundColor: mode === 'light' ? '#FFEBEE' : '#1F2937',
          color: mode === 'light' ? '#C62828' : '#FCA5A5',
          '&.MuiChip-outlined': {
            borderColor: mode === 'light' ? '#C62828' : '#FCA5A5',
            backgroundColor: 'transparent',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
          borderRadius: 12,
          boxShadow:
            mode === 'light'
              ? '0 2px 12px rgba(61, 61, 61, 0.15), 0 1px 4px rgba(61, 61, 61, 0.1)'
              : '0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2)',
        },
      },
    },
  },
  chartPalettes: {
    line: ['#50B9E0', '#FD6E12', '#2AA1CE', '#FDD803'], // Rhesis primary blue, orange, CTA blue, yellow
    pie: ['#97D5EE', '#50B9E0', '#2AA1CE'], // Rhesis light blue, primary blue, CTA blue
    status: ['#2E7D32', '#F57C00', '#C62828'], // success (green), warning (amber), error (red) - using light mode colors for consistency
  },
  elevation: {
    none: 0, // Flat surfaces, nested components
    subtle: 1, // Minimal elevation for standalone components
    standard: 2, // Standard elevation for cards, containers, charts
    prominent: 6, // High elevation for modals, important dialogs
    modal: 8, // Maximum elevation for overlays
  },
  customSpacing: {
    container: {
      small: 2, // 16px - for compact components
      medium: 3, // 24px - for standard containers
      large: 4, // 32px - for spacious layouts
    },
    section: {
      small: 2, // 16px - between related elements
      medium: 3, // 24px - between sections
      large: 4, // 32px - between major sections
    },
  },
  iconSizes: {
    small: 16, // Small icons (inline with text, form inputs)
    medium: 24, // Standard icons (buttons, navigation)
    large: 32, // Large icons (cards, headers)
    xlarge: 48, // Extra large icons (empty states, hero sections)
  },
});

// Create theme instances for both modes
const lightTheme = createTheme(getDesignTokens('light'));
const darkTheme = createTheme(getDesignTokens('dark'));

// Add custom theme extensions
declare module '@mui/material/styles' {
  interface TypographyVariants {
    chartLabel: React.CSSProperties;
    chartTick: React.CSSProperties;
    helperText: React.CSSProperties;
  }

  // Allow configuration using `createTheme`
  interface TypographyVariantsOptions {
    chartLabel?: React.CSSProperties;
    chartTick?: React.CSSProperties;
    helperText?: React.CSSProperties;
  }

  interface Theme {
    chartPalettes: {
      line: string[];
      pie: string[];
      status: string[];
    };
    elevation: {
      none: number;
      subtle: number;
      standard: number;
      prominent: number;
      modal: number;
    };
    shape: {
      borderRadius: number;
      sharp: number;
      circular: string;
    };
    customSpacing: {
      container: {
        small: number;
        medium: number;
        large: number;
      };
      section: {
        small: number;
        medium: number;
        large: number;
      };
    };
    iconSizes: {
      small: number;
      medium: number;
      large: number;
      xlarge: number;
    };
  }
  interface ThemeOptions {
    chartPalettes?: {
      line: string[];
      pie: string[];
      status: string[];
    };
    elevation?: {
      none: number;
      subtle: number;
      standard: number;
      prominent: number;
      modal: number;
    };
    customSpacing?: {
      container: {
        small: number;
        medium: number;
        large: number;
      };
      section: {
        small: number;
        medium: number;
        large: number;
      };
    };
    iconSizes?: {
      small: number;
      medium: number;
      large: number;
      xlarge: number;
    };
  }
  interface TypeBackground {
    light1?: string;
    light2?: string;
    light3?: string;
    light4?: string;
  }
}

// Update Typography component props to include custom variants
declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    chartLabel: true;
    chartTick: true;
    helperText: true;
  }
}

// Export light theme as default for backward compatibility
export default lightTheme;

// Export both theme instances and the getDesignTokens function
export { lightTheme, darkTheme, getDesignTokens };
