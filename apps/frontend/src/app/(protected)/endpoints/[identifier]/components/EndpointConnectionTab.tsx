'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import {
  LockIcon,
  VisibilityIcon,
  VisibilityOffIcon,
} from '@/components/icons';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { METHODS } from './endpoint-detail-shared';
import EndpointSdkConnectionPanel from './EndpointSdkConnectionPanel';

interface RestConnectionDraft {
  url: string;
  method: string;
}

interface AuthDraft {
  auth_token: string;
}

export default function EndpointConnectionTab() {
  const { endpoint, saveFields } = useEndpointDetailContext();
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [tokenFieldFocused, setTokenFieldFocused] = useState(false);
  const hasExistingToken = !!endpoint.id;

  const restInitial = useMemo(
    () => ({
      url: endpoint.url || '',
      method: endpoint.method || 'POST',
    }),
    [endpoint.url, endpoint.method]
  );

  const authInitial = useMemo(() => ({ auth_token: '' }), []);

  if (endpoint.connection_type === 'SDK') {
    return <EndpointSdkConnectionPanel />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <EditableSection<RestConnectionDraft>
        title="REST connection"
        initialValue={restInitial}
        onSave={async draft => {
          await saveFields({
            url: draft.url,
            method: draft.method,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 8 }}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="URL"
                  value={draft.url}
                  onChange={e =>
                    setDraft(prev => ({ ...prev, url: e.target.value }))
                  }
                />
              ) : (
                <ViewField label="URL" value={endpoint.url || '—'} />
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Method</InputLabel>
                  <Select
                    value={draft.method}
                    label="Method"
                    onChange={e =>
                      setDraft(prev => ({ ...prev, method: e.target.value }))
                    }
                  >
                    {METHODS.map(method => (
                      <MenuItem key={method} value={method}>
                        {method}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <ViewField label="Method" value={endpoint.method || '—'} />
              )}
            </Grid>
            <Grid size={12}>
              <ViewField
                label="Connection type"
                value={endpoint.connection_type}
              />
            </Grid>
          </Grid>
        )}
      </EditableSection>

      <EditableSection<AuthDraft>
        title="Authentication"
        initialValue={authInitial}
        isDirty={draft => draft.auth_token.trim() !== ''}
        onSave={async draft => {
          if (draft.auth_token === '') return;
          await saveFields({ auth_token: draft.auth_token });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <>
            {isEditing ? (
              <>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  Token will be encrypted and sent as{' '}
                  <code>Authorization: Bearer &lt;token&gt;</code>. Use{' '}
                  <code>{'{{ auth_token }}'}</code> in custom headers.
                </Typography>
                <TextField
                  fullWidth
                  label="API Token"
                  type={showAuthToken ? 'text' : 'password'}
                  value={
                    tokenFieldFocused || draft.auth_token !== ''
                      ? draft.auth_token
                      : hasExistingToken
                        ? '••••••••••••••••••••••••'
                        : ''
                  }
                  onChange={e =>
                    setDraft(prev => ({
                      ...prev,
                      auth_token: e.target.value,
                    }))
                  }
                  onFocus={() => {
                    setTokenFieldFocused(true);
                    if (draft.auth_token === '') {
                      setDraft({ auth_token: '' });
                    }
                  }}
                  onBlur={() => {
                    if (draft.auth_token === '') {
                      setTokenFieldFocused(false);
                    }
                  }}
                  placeholder={
                    hasExistingToken
                      ? 'Enter new token or leave empty to keep existing'
                      : 'sk-...'
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
                          onClick={() => setShowAuthToken(!showAuthToken)}
                          edge="end"
                        >
                          {showAuthToken ? (
                            <VisibilityOffIcon />
                          ) : (
                            <VisibilityIcon />
                          )}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                  helperText={
                    hasExistingToken
                      ? 'Leave empty to keep the existing token.'
                      : 'Token will be encrypted and stored securely.'
                  }
                />
              </>
            ) : (
              <ViewField
                label="API Token"
                value={
                  hasExistingToken
                    ? '••••••••••••••••••••••••'
                    : 'No token configured'
                }
              />
            )}
          </>
        )}
      </EditableSection>
    </Box>
  );
}
