import { Typography } from '@mui/material';
import { useAccessibilityMode } from '@/hooks/useAccessibilityMode';

/**
 * Tells keyboard users how to leave a code editor. Monaco keeps Tab for
 * indentation, so without this hint Tab looks like a keyboard trap (WCAG 2.1.2).
 * In accessibility mode the editors start with Tab moving focus instead.
 */
export default function EditorKeyboardHint() {
  const accessibilityMode = useAccessibilityMode();
  return (
    <Typography
      variant="caption"
      color="text.secondary"
      component="p"
      sx={{ mt: 0.5 }}
    >
      {accessibilityMode
        ? 'Tab moves to the next control. To indent with Tab, press Ctrl+M first (Ctrl+Shift+M on Mac).'
        : 'Tab indents. To move focus out with Tab, press Ctrl+M first (Ctrl+Shift+M on Mac).'}
    </Typography>
  );
}
