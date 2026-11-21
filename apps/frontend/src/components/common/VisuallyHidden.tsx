import { Box, type BoxProps } from '@mui/material';

/**
 * Content for screen readers only, e.g. a page heading on a screen that has
 * no visible title. Stays in the accessibility tree, takes no space.
 */
export default function VisuallyHidden({ sx, ...props }: BoxProps) {
  return (
    <Box
      sx={[
        {
          position: 'absolute',
          width: 1,
          height: 1,
          p: 0,
          m: -0.125,
          overflow: 'hidden',
          clip: 'rect(0 0 0 0)',
          whiteSpace: 'nowrap',
          border: 0,
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      {...props}
    />
  );
}
