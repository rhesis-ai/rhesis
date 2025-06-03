import { useTheme } from '@mui/material/styles';

/**
 * Hook to get chart colors from the theme
 * Returns primary and secondary palette colors with appropriate opacity variations
 */
export function useChartColors() {
  const theme = useTheme();
  
  // Create a palette of colors derived from the theme
  const themeColors = {
    // Primary colors (shades of primary)
    primary: theme.palette.primary.main,
    primaryLight: theme.palette.primary.light,
    primaryDark: theme.palette.primary.dark,
    
    // Secondary colors (shades of secondary)
    secondary: theme.palette.secondary.main,
    secondaryLight: theme.palette.secondary.light,
    secondaryDark: theme.palette.secondary.dark,
    
    // Extended palette based on primary/secondary with opacity
    // Using rgba to add transparency to colors
    primaryTransparent: `${theme.palette.primary.main}99`, // 60% opacity
    secondaryTransparent: `${theme.palette.secondary.main}99`, // 60% opacity
    
    // Status colors
    success: theme.palette.success?.main || '#82ca9d',
    error: theme.palette.error?.main || '#ff6347',
    warning: theme.palette.warning?.main || '#ffc658',
    info: theme.palette.info?.main || '#8884d8',
    
    // Neutral colors
    grey1: theme.palette.grey[100],
    grey5: theme.palette.grey[500],
    grey9: theme.palette.grey[900],
  };
  
  // Predefined palettes for different chart types
  const palettes = {
    // For line charts (good for multiple series)
    line: [
      themeColors.primary,
      themeColors.secondary,
      themeColors.success,
      themeColors.info,
      themeColors.warning,
    ],
    
    // For pie/donut charts
    pie: [
      themeColors.primary,
      themeColors.secondary,
      themeColors.warning,
      themeColors.info,
      themeColors.primaryTransparent,
      themeColors.secondaryTransparent,
    ],
    
    // For status-related charts (success/failure/etc)
    status: [
      themeColors.success,
      themeColors.error,
      themeColors.warning,
      themeColors.info,
    ]
  };
  
  return {
    themeColors,
    palettes
  };
} 