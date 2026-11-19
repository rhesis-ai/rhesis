import { Typography } from '@mui/material';

/**
 * Tells keyboard users how to leave a code editor. Monaco keeps Tab for
 * indentation, so without this hint Tab looks like a keyboard trap (WCAG 2.1.2).
 */
export default function EditorKeyboardHint() {
  return (
    <Typography
      variant="caption"
      color="text.secondary"
      component="p"
      sx={{ mt: 0.5 }}
    >
      Tab indents. To move focus out with Tab, press Ctrl+M first (Ctrl+Shift+M
      on Mac).
    </Typography>
  );
}
