'use client';

import { Box, Chip, Typography } from '@mui/material';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import ViewField from '@/components/common/ViewField';
import {
  ENDPOINT_AUTH_TYPES,
  type EndpointAuthType,
} from '@/constants/endpoint-auth';
import HeadersEditor from './HeadersEditor';
import CustomHeadersField from './CustomHeadersField';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import EndpointAuthFields from './EndpointAuthFields';
import SecretField, { STORED_MASK } from './SecretField';
import type { ClientCredentialsDraft } from './endpointAuth';
import { variableChipSx } from './endpoint-styles';

export interface EndpointHeadersFieldsProps {
  authType: EndpointAuthType;
  onAuthTypeChange: (value: EndpointAuthType) => void;
  clientCredentials: ClientCredentialsDraft;
  onClientCredentialsChange: (value: ClientCredentialsDraft) => void;
  hasExistingClientSecret?: boolean;
  authToken: string;
  requestHeaders: string;
  onAuthTokenChange: (value: string) => void;
  onRequestHeadersChange: (value: string) => void;
  editorTheme: string;
  isEditing: boolean;
  hasExistingToken?: boolean;
  tokenCleared?: boolean;
  onToggleTokenCleared?: () => void;
  editorWrapperStyle?: Record<string, unknown>;
  /** Edit headers as key/value rows first, with JSON one click away. */
  easyHeaderInput?: boolean;
}

export default function EndpointHeadersFields({
  authType,
  onAuthTypeChange,
  clientCredentials,
  onClientCredentialsChange,
  hasExistingClientSecret = false,
  authToken,
  requestHeaders,
  onAuthTokenChange,
  onRequestHeadersChange,
  editorTheme,
  isEditing,
  hasExistingToken = false,
  tokenCleared = false,
  onToggleTokenCleared,
  editorWrapperStyle,
  easyHeaderInput = false,
}: EndpointHeadersFieldsProps) {
  const isBearer = authType === ENDPOINT_AUTH_TYPES.BEARER_TOKEN;
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
      {easyHeaderInput ? 'in the headers below.' : 'in the editor below.'}
    </Box>
  );

  const bearerTokenField = isEditing ? (
    <SecretField
      label="API Token (optional)"
      noun="token"
      value={authToken}
      onChange={onAuthTokenChange}
      hasStored={hasExistingToken}
      placeholder="sk-..."
      helperText={tokenHelper}
      cleared={tokenCleared}
      onToggleCleared={onToggleTokenCleared}
    />
  ) : (
    <ViewField
      label="API Token"
      value={hasExistingToken ? STORED_MASK : 'No token configured'}
    />
  );

  return (
    <Box>
      <EndpointAuthFields
        authType={authType}
        onAuthTypeChange={onAuthTypeChange}
        clientCredentials={clientCredentials}
        onClientCredentialsChange={onClientCredentialsChange}
        hasStoredClientSecret={hasExistingClientSecret}
        isEditing={isEditing}
        editorTheme={editorTheme}
        editorWrapperStyle={editorWrapperStyle}
        bearerTokenField={bearerTokenField}
      />

      <Box sx={{ mt: 1, mb: 2 }}>
        <FormSectionDivider
          headline="Custom headers"
          descriptiveText="Add headers Rhesis should include on every request."
        />
      </Box>

      {isEditing && easyHeaderInput ? (
        <CustomHeadersField
          authToken={isBearer ? authToken : ''}
          requestHeaders={requestHeaders}
          onChange={onRequestHeadersChange}
          editorTheme={editorTheme}
        />
      ) : isEditing ? (
        <HeadersEditor
          // Only a typed bearer token adds an Authorization header here; the
          // backend adds one for an OAuth token when no header sets it.
          authToken={isBearer ? authToken : ''}
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
            in header values to reference the{' '}
            {isBearer ? 'API token' : 'access token'}.
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
