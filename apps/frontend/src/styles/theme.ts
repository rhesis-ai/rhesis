'use client';
import { createTheme, PaletteMode } from '@mui/material/styles';
import React from 'react';

// Import design tokens from the server-safe constants file.
// Re-export so that existing imports from '@/styles/theme' continue to work.
import {
  GREYSCALE,
  BORDER_RADIUS,
  BACKDROP_COLORS,
  ELEVATION,
  FAB_GROUP_GAP,
} from './theme-constants';
export { GREYSCALE, BORDER_RADIUS, BACKDROP_COLORS, ELEVATION, FAB_GROUP_GAP };

// Define theme settings for both light and dark modes
const getDesignTokens = (mode: PaletteMode) => {
  const gs = mode === 'light' ? GREYSCALE.light : GREYSCALE.dark;

  return {
    palette: {
      mode,
      ...(mode === 'light'
        ? {
            // Light mode - Rhesis AI colors
            primary: {
              main: '#0080AF', // Figma primary blue
              light: '#33A6CB', // lighter tint
              dark: '#005F82', // darker shade
              contrastText: '#FFFFFF',
            },
            secondary: {
              main: '#FD6E12', // Secondary CTA Orange
              light: '#FDD803', // Accent Yellow
              dark: '#1A1A1A', // Dark Black
              contrastText: '#FFFFFF',
            },
            background: {
              default: '#FFFFFF',
              paper: '#FFFFFF',
              light1: '#F2F9FD',
              light2: '#E4F2FA',
              light3: '#C2E5F5',
              light4: '#33A6CB',
            },
            text: {
              primary: '#3D3D3D',
              secondary: '#1A1A1A',
            },
            success: {
              main: '#38ad87',
              contrastText: '#FFFFFF',
            },
            warning: {
              main: '#F57C00',
              contrastText: '#FFFFFF',
            },
            error: {
              main: '#de3355',
              contrastText: '#FFFFFF',
            },
          }
        : {
            // Dark mode
            primary: {
              main: '#33A6CB', // slightly lighter for dark bg readability
              light: '#66C2DC',
              dark: '#0080AF',
              contrastText: '#FFFFFF',
            },
            secondary: {
              main: '#FD6E12',
              light: '#F78166',
              dark: '#58A6FF',
              contrastText: '#FFFFFF',
            },
            background: {
              default: '#0D1117',
              paper: '#161B22',
              light1: '#0D1117',
              light2: '#161B22',
              light3: '#1F242B',
              light4: '#2C2C2C',
            },
            text: {
              primary: '#E6EDF3',
              secondary: '#A9B1BB',
            },
            success: {
              main: '#86EFAC',
              contrastText: '#000000',
            },
            warning: {
              main: '#FCD34D',
              contrastText: '#000000',
            },
            error: {
              main: '#FCA5A5',
              contrastText: '#000000',
            },
          }),
      // Greyscale ramp available on palette for both modes
      greyscale: gs,
    },
    shape: {
      borderRadius: 8,
      sharp: 0,
      circular: '50%',
    },
    typography: {
      fontFamily:
        '"Be Vietnam Pro", "Roboto", "Helvetica", "Arial", sans-serif',
      fontFamilyCode:
        '"SFMono-Regular", "Consolas", "Liberation Mono", "Menlo", monospace',
      h1: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 800,
        fontSize: '3rem', // 48px
        lineHeight: '57.6px',
        color: gs.title,
      },
      h2: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 800,
        fontSize: '2.5rem', // 40px
        lineHeight: '48px',
        color: gs.title,
      },
      h3: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 800,
        fontSize: '2.0625rem', // 33px
        lineHeight: '39.6px',
        color: gs.title,
      },
      h4: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 700,
        fontSize: '1.75rem', // 28px – Figma H4/Bold
        lineHeight: '33.6px',
        color: gs.title,
      },
      h5: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 700,
        fontSize: '1.4375rem', // 23px
        lineHeight: '27.6px',
        color: gs.title,
      },
      h6: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 600,
        fontSize: '1.25rem', // 20px
        lineHeight: '24px',
        color: gs.title,
      },
      body1: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '1rem', // 16px
        lineHeight: '24px',
        color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
      },
      body2: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.875rem', // 14px
        lineHeight: '22px',
        color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
      },
      button: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 600,
        textTransform: 'none' as const,
        fontSize: '0.875rem', // 14px
      },
      caption: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.75rem', // 12px
        lineHeight: '18px',
        color: gs.subtitle,
      },
      subtitle1: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 500,
        fontSize: '1rem',
        lineHeight: 1.75,
        color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
      },
      subtitle2: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 500,
        fontSize: '0.875rem',
        lineHeight: 1.57,
        color: mode === 'light' ? '#3D3D3D' : '#E6EDF3',
      },
      overline: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 600,
        fontSize: '0.75rem',
        lineHeight: '18px',
        letterSpacing: '0.04em',
        textTransform: 'uppercase' as const,
        color: gs.subtitle,
      },
      // ── Figma-aligned custom variants ──────────────────────────────────
      bodyLReg: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '1rem', // 16px
        lineHeight: '24px',
        color: gs.body,
      },
      bodyMReg: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.875rem', // 14px
        lineHeight: '22px',
        color: gs.body,
      },
      bodyMBold: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 700,
        fontSize: '0.875rem', // 14px
        lineHeight: '22px',
        color: gs.body,
      },
      bodySReg: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.75rem', // 12px
        lineHeight: '18px',
        color: gs.body,
      },
      captionBold: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 600,
        fontSize: '0.75rem', // 12px
        lineHeight: '18px',
        color: gs.body,
      },
      // ── Legacy custom variants (kept for backwards-compat) ──────────────
      chartLabel: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.75rem',
        lineHeight: 1.5,
        color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
      },
      chartTick: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.625rem',
        lineHeight: 1.4,
        color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
      },
      helperText: {
        fontFamily: '"Be Vietnam Pro", sans-serif',
        fontWeight: 400,
        fontSize: '0.875rem',
        lineHeight: 1.43,
        color: mode === 'light' ? '#3D3D3D' : '#FFFFFF',
      },
      markdownH1Scale: '1.4em',
      markdownH2Scale: '1.25em',
      markdownH3Scale: '1.1em',
      markdownH4Scale: '1em',
    },
    components: {
      MuiSvgIcon: {
        styleOverrides: {
          root: {
            fontWeight: 200,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#0080AF' : '#161B22',
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
              color: gs.body,
              boxShadow: mode === 'light' ? ELEVATION.xs : 'none',
            },
            '& .MuiSvgIcon-root': {
              color: mode === 'light' ? gs.body : '#FFFFFF',
            },
            '& .MuiAvatar-root .MuiSvgIcon-root': {
              color: 'inherit',
            },
            '& .MuiButton-icon .MuiSvgIcon-root, & .MuiButton-startIcon .MuiSvgIcon-root, & .MuiButton-endIcon .MuiSvgIcon-root':
              {
                color: 'inherit',
              },
            '& .MuiListItemButton-root.Mui-selected': {
              backgroundColor: '#0080AF',
              '& .MuiSvgIcon-root': { color: '#FFFFFF' },
              '& .MuiTypography-root': { color: '#FFFFFF' },
            },
            '& .MuiDivider-root': {
              margin: '16px 0',
              borderColor: mode === 'light' ? gs.border : '#2C2C2C',
            },
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
          },
          elevation1: {
            boxShadow: ELEVATION.xs,
          },
          elevation2: {
            boxShadow: ELEVATION.s,
          },
          elevation6: {
            boxShadow: ELEVATION.m,
          },
          elevation8: {
            boxShadow: ELEVATION.l,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            fontFamily: '"Be Vietnam Pro", sans-serif',
            fontWeight: 600,
            borderRadius: 8,
            '&.MuiButton-containedPrimary': {
              backgroundColor: '#0080AF',
              color: '#FFFFFF',
              '&:hover': { backgroundColor: '#005F82' },
              '&.Mui-disabled': { backgroundColor: 'unset', color: 'unset' },
            },
            '&.MuiButton-containedSecondary': {
              backgroundColor: '#FD6E12',
              color: '#FFFFFF',
              '&:hover': { backgroundColor: '#FDD803', color: '#1A1A1A' },
            },
            '&.MuiButton-outlinedPrimary': {
              color: mode === 'dark' ? '#33A6CB' : '#0080AF',
              borderColor: mode === 'dark' ? '#33A6CB' : '#0080AF',
              backgroundColor: 'transparent',
              '&:hover': {
                backgroundColor: mode === 'dark' ? '#33A6CB' : '#0080AF',
                color: '#FFFFFF',
                borderColor: mode === 'dark' ? '#33A6CB' : '#0080AF',
              },
            },
            '&.MuiButton-outlinedSecondary': {
              color: '#FD6E12',
              borderColor: '#FD6E12',
              backgroundColor: 'transparent',
              '&:hover': {
                backgroundColor: '#FD6E12',
                color: '#FFFFFF',
                borderColor: '#FD6E12',
              },
            },
            '&.MuiButton-textPrimary': {
              color: mode === 'light' ? '#0080AF' : '#33A6CB',
              '&:hover': {
                backgroundColor:
                  mode === 'light' ? 'rgba(0, 128, 175, 0.04)' : '#1F242B',
              },
            },
          },
        },
        variants: [
          {
            // 'pill' is registered in ButtonPropsVariantOverrides below
            props: { variant: 'pill' as const },
            style: {
              borderRadius: 999,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
              lineHeight: '22px',
              paddingLeft: '16px',
              paddingRight: '16px',
              border: `1px solid ${mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border}`,
              color:
                mode === 'light' ? GREYSCALE.light.body : GREYSCALE.dark.body,
              backgroundColor: 'transparent',
              '&.active, &[aria-pressed="true"]': {
                backgroundColor: '#0080AF',
                color: '#FFFFFF',
                borderColor: '#0080AF',
              },
              '&:hover': {
                backgroundColor:
                  mode === 'light'
                    ? GREYSCALE.light.surface1
                    : GREYSCALE.dark.surface1,
              },
            },
          },
        ],
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontFamily: '"Be Vietnam Pro", sans-serif',
            fontWeight: 500,
            // Tags and interactive chips stay rectangular; use GridBadge for pill badges.
            borderRadius: 4,
            fontSize: '0.75rem',
            paddingTop: '6px',
            paddingBottom: '6px',
            paddingLeft: '10px',
            paddingRight: '10px',
          },
          colorDefault: {
            backgroundColor:
              mode === 'light' ? GREYSCALE.light.surface2 : '#2C2C2C',
            color: mode === 'light' ? GREYSCALE.light.body : '#E6EDF3',
            '&.MuiChip-outlined': {
              borderColor:
                mode === 'light' ? GREYSCALE.light.border : '#404040',
              backgroundColor: 'transparent',
            },
          },
          colorInfo: {
            backgroundColor: mode === 'light' ? '#E4F2FA' : '#1F2937',
            color: mode === 'light' ? '#1565C0' : '#93C5FD',
            '&.MuiChip-outlined': {
              borderColor: mode === 'light' ? '#90CAF9' : '#3B82F6',
              backgroundColor: 'transparent',
            },
          },
          colorSuccess: {
            backgroundColor: mode === 'light' ? '#E8F5E8' : '#1F2937',
            color: mode === 'light' ? '#2E7D32' : '#86EFAC',
            '&.MuiChip-outlined': {
              borderColor: mode === 'light' ? '#2E7D32' : '#86EFAC',
              backgroundColor: 'transparent',
            },
          },
          colorWarning: {
            backgroundColor: mode === 'light' ? '#FFF8E1' : '#1F2937',
            color: mode === 'light' ? '#F57C00' : '#FCD34D',
            '&.MuiChip-outlined': {
              borderColor: mode === 'light' ? '#F57C00' : '#FCD34D',
              backgroundColor: 'transparent',
            },
          },
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
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            fontFamily: '"Be Vietnam Pro", sans-serif',
            fontSize: '0.75rem', // 12px
            lineHeight: 1.4,
            padding: '6px 10px',
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#1C2128',
            color: mode === 'light' ? '#1C2128' : '#E6EDF3',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          },
          arrow: {
            color: mode === 'light' ? '#FFFFFF' : '#1C2128',
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#161B22',
            borderRadius: 12,
            boxShadow: ELEVATION.xs,
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border}`,
            fontFamily: '"Be Vietnam Pro", sans-serif',
            fontSize: '0.875rem', // 14px
            color:
              mode === 'light' ? GREYSCALE.light.body : GREYSCALE.dark.body,
            padding: '0 16px',
            height: '48px',
          },
          head: {
            backgroundColor:
              mode === 'light'
                ? GREYSCALE.light.surface1
                : GREYSCALE.dark.surface1,
            fontWeight: 600,
            color:
              mode === 'light' ? GREYSCALE.light.body : GREYSCALE.dark.body,
            height: '48px',
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            height: '48px',
            '&:hover': {
              backgroundColor:
                mode === 'light'
                  ? GREYSCALE.light.surface1
                  : GREYSCALE.dark.surface1,
            },
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 8,
              ...(mode === 'dark' && {
                backgroundColor: GREYSCALE.dark.fieldSurface,
              }),
              '& fieldset': {
                borderColor:
                  mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
              '&:hover fieldset': {
                borderColor: '#0080AF',
              },
            },
            ...(mode === 'dark' && {
              '& .MuiInputLabel-root': { color: GREYSCALE.dark.subtitle },
              '& .MuiFormHelperText-root': { color: GREYSCALE.dark.subtitle },
            }),
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            ...(mode === 'dark' && {
              backgroundColor: GREYSCALE.dark.fieldSurface,
              color: '#ffffff',
            }),
          },
          notchedOutline: {
            borderColor:
              mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border,
          },
          input: {
            ...(mode === 'dark' && { color: '#ffffff' }),
          },
        },
      },
      MuiAutocomplete: {
        styleOverrides: {
          // MUI Autocomplete default uses padding:9px on inputRoot, making the
          // field ~44px tall. TextField/Select are ~56px. The InputLabel
          // transform (translate(14px,16.5px)) is calibrated for ~56px, so in
          // the shorter Autocomplete box the label sits below visual centre.
          // Setting minHeight to match ensures the label is properly centred.
          inputRoot: {
            minHeight: '56px',
          },
        },
      },
    },
    chartPalettes: {
      line: ['#0080AF', '#FD6E12', '#33A6CB', '#FDD803'],
      pie: ['#33A6CB', '#0080AF', '#005F82'],
      status: ['#2E7D32', '#F57C00', '#C62828'],
      categorical: [
        '#50B9E0',
        '#2AA1CE',
        '#FD6E12',
        '#FDD803',
        '#97D5EE',
        '#2E7D32',
        '#F57C00',
        '#C62828',
        '#1A1A1A',
        '#3D3D3D',
        '#58A6FF',
        '#F78166',
        '#86EFAC',
        '#FCD34D',
        '#FCA5A5',
        '#3BC4F2',
      ],
    },
    elevation: {
      none: 0,
      subtle: 1,
      standard: 2,
      prominent: 6,
      modal: 8,
      xs: ELEVATION.xs,
    },
    customSpacing: {
      container: { small: 2, medium: 3, large: 4 },
      section: { small: 2, medium: 3, large: 4 },
    },
    iconSizes: {
      small: 16,
      medium: 24,
      large: 32,
      xlarge: 48,
    },
  };
};

const lightTheme = createTheme(getDesignTokens('light'));
const darkTheme = createTheme(getDesignTokens('dark'));

declare module '@mui/material/styles' {
  interface TypographyVariants {
    fontFamilyCode: string;
    // Figma-aligned variants
    bodyLReg: React.CSSProperties;
    bodyMReg: React.CSSProperties;
    bodyMBold: React.CSSProperties;
    bodySReg: React.CSSProperties;
    captionBold: React.CSSProperties;
    // Legacy variants
    chartLabel: React.CSSProperties;
    chartTick: React.CSSProperties;
    helperText: React.CSSProperties;
    markdownH1Scale: string;
    markdownH2Scale: string;
    markdownH3Scale: string;
    markdownH4Scale: string;
  }
  interface TypographyVariantsOptions {
    fontFamilyCode?: string;
    bodyLReg?: React.CSSProperties;
    bodyMReg?: React.CSSProperties;
    bodyMBold?: React.CSSProperties;
    bodySReg?: React.CSSProperties;
    captionBold?: React.CSSProperties;
    chartLabel?: React.CSSProperties;
    chartTick?: React.CSSProperties;
    helperText?: React.CSSProperties;
    markdownH1Scale?: string;
    markdownH2Scale?: string;
    markdownH3Scale?: string;
    markdownH4Scale?: string;
  }
  interface Theme {
    chartPalettes: {
      line: string[];
      pie: string[];
      status: string[];
      categorical: string[];
    };
    elevation: {
      none: number;
      subtle: number;
      standard: number;
      prominent: number;
      modal: number;
      xs: string;
    };
    shape: { borderRadius: number; sharp: number; circular: string };
    customSpacing: {
      container: { small: number; medium: number; large: number };
      section: { small: number; medium: number; large: number };
    };
    iconSizes: { small: number; medium: number; large: number; xlarge: number };
  }
  interface ThemeOptions {
    chartPalettes?: {
      line: string[];
      pie: string[];
      status: string[];
      categorical: string[];
    };
    elevation?: {
      none?: number;
      subtle?: number;
      standard?: number;
      prominent?: number;
      modal?: number;
      xs?: string;
    };
    customSpacing?: {
      container?: { small: number; medium: number; large: number };
      section?: { small: number; medium: number; large: number };
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
  interface Palette {
    greyscale: {
      title: string;
      body: string;
      label: string;
      subtitle: string;
      border: string;
      surface1: string;
      surface2: string;
      fieldSurface: string;
    };
  }
  interface PaletteOptions {
    greyscale?: {
      title?: string;
      body?: string;
      label?: string;
      subtitle?: string;
      border?: string;
      surface1?: string;
      surface2?: string;
      fieldSurface?: string;
    };
  }
}

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    bodyLReg: true;
    bodyMReg: true;
    bodyMBold: true;
    bodySReg: true;
    captionBold: true;
    chartLabel: true;
    chartTick: true;
    helperText: true;
  }
}

declare module '@mui/material/Button' {
  interface ButtonPropsVariantOverrides {
    pill: true;
  }
}

export default lightTheme;
export { lightTheme, darkTheme, getDesignTokens };
