'use client';

import {
  Box,
  Chip,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import ViewField from '@/components/common/ViewField';
import {
  LockIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';
import HeadersEditor from './HeadersEditor';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import { variableChipSx } from './endpoint-styles';

export interface EndpointHeadersFieldsProps {
  authToken: string;
  requestHeaders: string;
  onAuthTokenChange: (value: string) => void;
  onRequestHeadersChange: (value: string) => void;
  showAuthToken: boolean;
  onToggleAuthToken: () => void;
  editorTheme: string;
  isEditing: boolean;
  hasExistingToken?: boolean;
  tokenFieldFocused?: boolean;
  onTokenFocus?: () => void;
  onTokenBlur?: () => void;
  editorWrapperStyle?: Record<string, unknown>;
}

export default function EndpointHeadersFields({
  authToken,
  requestHeaders,
  onAuthTokenChange,
  onRequestHeadersChange,
  showAuthToken,
  onToggleAuthToken,
  editorTheme,
  isEditing,
  hasExistingToken = false,
  tokenFieldFocused = false,
  onTokenFocus,
  onTokenBlur,
  editorWrapperStyle,
}: EndpointHeadersFieldsProps) {
  const tokenHelper = (
    <Box
      component="span"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        flexWrap: 'wrap',
      }}
    >
      Stored as
      <Chip
        label="{{ auth_token }}"
        size="small"
        component="span"
        sx={{
          ...variableChipSx,
          height: 18,
          '& .MuiChip-label': { px: 0.75 },
        }}
      />
      in the editor below.
    </Box>
  );

  return (
    <Box>
      {isEditing ? (
        <TextField
          fullWidth
          label="API Token (optional)"
          type={showAuthToken ? 'text' : 'password'}
          value={
            tokenFieldFocused || authToken !== ''
              ? authToken
              : hasExistingToken
                ? '••••••••••••••••••••••••'
                : ''
          }
          onChange={e => onAuthTokenChange(e.target.value)}
          onFocus={onTokenFocus}
          onBlur={onTokenBlur}
          placeholder={
            hasExistingToken
              ? 'Enter new token or leave empty to keep existing'
              : 'sk-...'
          }
          sx={{ mb: 3 }}
          helperText={
            hasExistingToken
              ? 'Leave empty to keep the existing token.'
              : tokenHelper
          }
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <LockIcon color="action" />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  aria-label="toggle token visibility"
                  onClick={onToggleAuthToken}
                  edge="end"
                >
                  {showAuthToken ? <VisibilityOffIcon /> : <VisibilityIcon />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      ) : (
        <Box sx={{ mb: 3 }}>
          <ViewField
            label="API Token"
            value={
              hasExistingToken
                ? '••••••••••••••••••••••••'
                : 'No token configured'
            }
          />
        </Box>
      )}

      <Box sx={{ mt: 1, mb: 2 }}>
        <FormSectionDivider
          headline="Custom headers"
          descriptiveText="Add headers Rhesis should include on every request."
        />
      </Box>

      {isEditing ? (
        <HeadersEditor
          authToken={authToken}
          customHeaders={requestHeaders}
          onChange={onRequestHeadersChange}
          editorTheme={editorTheme}
        />
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Use{' '}
            <Chip
              label="{{ auth_token }}"
              size="small"
              component="span"
              sx={{
                ...variableChipSx,
                height: 20,
                verticalAlign: 'middle',
                '& .MuiChip-label': { px: 0.75 },
              }}
            />{' '}
            in header values to reference the API token.
          </Typography>
          <JsonMonacoField
            editorKey="request-headers-view"
            height="200px"
            theme={editorTheme}
            wrapperSx={editorWrapperStyle}
            readOnly
            value={requestHeaders}
            onChange={() => undefined}
          />
        </>
      )}
    </Box>
  );
}
