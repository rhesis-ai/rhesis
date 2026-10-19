'use client';

import React from 'react';
import {
  Box,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import ViewField from '@/components/common/ViewField';
import {
  ENDPOINT_AUTH_TYPES,
  ENDPOINT_AUTH_TYPE_LABELS,
  type EndpointAuthType,
} from '@/constants/endpoint-auth';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import SecretField, { STORED_MASK } from './SecretField';
import { parseExtraPayload, type ClientCredentialsDraft } from './endpointAuth';

export interface EndpointAuthFieldsProps {
  authType: EndpointAuthType;
  onAuthTypeChange: (value: EndpointAuthType) => void;
  clientCredentials: ClientCredentialsDraft;
  onClientCredentialsChange: (value: ClientCredentialsDraft) => void;
  hasStoredClientSecret?: boolean;
  isEditing: boolean;
  editorTheme: string;
  editorWrapperStyle?: Record<string, unknown>;
  // The bearer token field, rendered when that type is selected.
  bearerTokenField: React.ReactNode;
}

const AUTH_TYPE_OPTIONS = Object.values(ENDPOINT_AUTH_TYPES);

function isValidUrl(url: string) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export default function EndpointAuthFields({
  authType,
  onAuthTypeChange,
  clientCredentials,
  onClientCredentialsChange,
  hasStoredClientSecret = false,
  isEditing,
  editorTheme,
  editorWrapperStyle,
  bearerTokenField,
}: EndpointAuthFieldsProps) {
  const isClientCredentials =
    authType === ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS;
  const set = (field: keyof ClientCredentialsDraft) => (value: string) =>
    onClientCredentialsChange({ ...clientCredentials, [field]: value });

  if (!isEditing) {
    return (
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={12}>
          <ViewField
            label="Authentication"
            value={ENDPOINT_AUTH_TYPE_LABELS[authType]}
          />
        </Grid>
        {isClientCredentials ? (
          <>
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField
                label="Token URL"
                value={clientCredentials.token_url || '—'}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField
                label="Client ID"
                value={clientCredentials.client_id || '—'}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField
                label="Client secret"
                value={
                  hasStoredClientSecret ? STORED_MASK : 'No secret configured'
                }
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField
                label="Audience"
                value={clientCredentials.audience || '—'}
              />
            </Grid>
            <Grid size={12}>
              <ViewField
                label="Scopes"
                value={clientCredentials.scopes || '—'}
              />
            </Grid>
            {clientCredentials.extra_payload && (
              <Grid size={12}>
                <ViewField
                  label="Extra payload"
                  value={clientCredentials.extra_payload}
                />
              </Grid>
            )}
          </>
        ) : (
          <Grid size={12}>{bearerTokenField}</Grid>
        )}
      </Grid>
    );
  }

  const tokenUrlInvalid = Boolean(
    clientCredentials.token_url && !isValidUrl(clientCredentials.token_url)
  );
  const extraPayload = parseExtraPayload(clientCredentials.extra_payload);

  return (
    <Box sx={{ mb: 3 }}>
      <FormControl fullWidth sx={{ mb: 3 }}>
        <InputLabel id="endpoint-auth-type-label">Authentication</InputLabel>
        <Select
          labelId="endpoint-auth-type-label"
          label="Authentication"
          value={authType}
          onChange={e => onAuthTypeChange(e.target.value as EndpointAuthType)}
        >
          {AUTH_TYPE_OPTIONS.map(option => (
            <MenuItem key={option} value={option}>
              {ENDPOINT_AUTH_TYPE_LABELS[option]}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {isClientCredentials ? (
        <Grid container spacing={2}>
          <Grid size={12}>
            <TextField
              fullWidth
              required
              label="Token URL"
              value={clientCredentials.token_url}
              onChange={e => set('token_url')(e.target.value)}
              placeholder="https://your-domain.auth0.com/oauth/token"
              error={tokenUrlInvalid}
              helperText={tokenUrlInvalid ? 'Enter a valid URL' : undefined}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              required
              label="Client ID"
              value={clientCredentials.client_id}
              onChange={e => set('client_id')(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <SecretField
              label="Client secret"
              noun="client secret"
              required
              value={clientCredentials.client_secret}
              onChange={set('client_secret')}
              hasStored={hasStoredClientSecret}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Audience (optional)"
              value={clientCredentials.audience}
              onChange={e => set('audience')(e.target.value)}
              placeholder="https://api.example.com"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Scopes (optional)"
              value={clientCredentials.scopes}
              onChange={e => set('scopes')(e.target.value)}
              placeholder="read:data write:data"
              helperText="Separate scopes with spaces"
            />
          </Grid>
          <Grid size={12}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Extra payload (optional): more fields for the token request, as a
              JSON object of strings.
            </Typography>
            <JsonMonacoField
              editorKey="client-credentials-extra-payload"
              height="120px"
              theme={editorTheme}
              wrapperSx={editorWrapperStyle}
              value={clientCredentials.extra_payload}
              onChange={value => set('extra_payload')(value ?? '')}
            />
            {'error' in extraPayload && (
              <Typography variant="caption" color="error">
                {extraPayload.error}
              </Typography>
            )}
          </Grid>
          <Grid size={12}>
            <Typography variant="body2" color="text.secondary">
              Rhesis requests a token from the token URL, caches it and
              refreshes it when it expires. It is sent as a bearer token, and{' '}
              {'{{ auth_token }}'} in headers holds it.
            </Typography>
          </Grid>
        </Grid>
      ) : (
        bearerTokenField
      )}
    </Box>
  );
}
