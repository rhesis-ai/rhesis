'use client';

import {
  Box,
  Button,
  TextField,
  Paper,
  Typography,
  useTheme,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import { useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestExecutableFieldProps {
  sessionToken: string;
  testId: string;
  promptId: string;
  initialContent: string;
  onUpdate?: () => void;
  fieldName?: 'content' | 'expected_response';
}

export default function TestExecutableField({
  sessionToken,
  testId,
  promptId,
  initialContent,
  onUpdate,
  fieldName = 'content',
}: TestExecutableFieldProps) {
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(initialContent);
  const [isUpdating, setIsUpdating] = useState(false);
  const { show: showNotification } = useNotifications();

  // Default rows for TextField and minHeight calculation
  const displayRows = 4;
  // Approx line height for monospace font, adjust if necessary
  const lineHeight = '1.4375em';
  // Padding for the display box (theme.spacing(1) = 8px)
  const boxPadding = '8px';
  // Min height for display box, considering rows and padding
  const displayMinHeight = `calc(${displayRows} * ${lineHeight} + 2 * ${boxPadding})`;
  // Space for the edit button
  const editButtonSpace = '80px';

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedContent(initialContent);
  };

  const handleConfirmEdit = async () => {
    if (!sessionToken) return;

    setIsUpdating(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const promptsClient = clientFactory.getPromptsClient();

      await promptsClient.updatePrompt(promptId, {
        [fieldName]: editedContent.trim(),
        language_code: 'en', // Maintain existing language code
      });

      setIsEditing(false);
      showNotification(
        `Successfully updated test ${fieldName.replace('_', ' ')}`,
        { severity: 'success' }
      );
      onUpdate?.();
    } catch (_error) {
      showNotification(`Failed to update test ${fieldName.replace('_', ' ')}`, {
        severity: 'error',
      });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Box sx={{ position: 'relative' }}>
      {isEditing ? (
        <TextField
          fullWidth
          multiline
          rows={displayRows} // Use the constant
          value={editedContent}
          onChange={e => setEditedContent(e.target.value)}
          sx={{ mb: 1 }} // Margin for confirm/cancel buttons
          autoFocus
        />
      ) : (
        <Typography
          component="pre"
          variant="body2"
          sx={{
            whiteSpace: 'pre-wrap',
            fontFamily: 'monospace',
            bgcolor: 'action.hover',
            borderRadius: theme => theme.shape.borderRadius * 0.25,
            padding: boxPadding,
            minHeight: displayMinHeight,
            // Ensure text does not go under the absolutely positioned Edit button
            paddingRight: editButtonSpace,
            // Break long words to prevent overflow if absolutely necessary,
            // though pre-wrap should handle most cases.
            wordBreak: 'break-word',
          }}
        >
          {initialContent || ' '}{' '}
          {/* Display a space if content is empty to render the box */}
        </Typography>
      )}

      {!isEditing ? (
        <Button
          startIcon={<EditIcon />}
          onClick={handleEdit}
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            zIndex: 1,
            backgroundColor: theme =>
              theme.palette.mode === 'dark'
                ? 'rgba(0, 0, 0, 0.6)'
                : 'rgba(255, 255, 255, 0.8)',
            '&:hover': {
              backgroundColor: theme =>
                theme.palette.mode === 'dark'
                  ? 'rgba(0, 0, 0, 0.8)'
                  : 'rgba(255, 255, 255, 0.9)',
            },
          }}
        >
          Edit
        </Button>
      ) : (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={handleCancelEdit}
            disabled={isUpdating}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<CheckIcon />}
            onClick={handleConfirmEdit}
            disabled={isUpdating}
          >
            Confirm
          </Button>
        </Box>
      )}
    </Box>
  );
}
