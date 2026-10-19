import { ENDPOINT_AUTH_TYPES } from '@/constants/endpoint-auth';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import {
  EMPTY_CLIENT_CREDENTIALS,
  authPayload,
  authTypeOf,
  clientCredentialsFromEndpoint,
  parseExtraPayload,
  testAuthFields,
  validateClientCredentials,
} from '../endpointAuth';

const filled = {
  ...EMPTY_CLIENT_CREDENTIALS,
  token_url: 'https://auth.example.com/oauth/token',
  client_id: 'client-123',
  client_secret: 'secret',
};

describe('authTypeOf', () => {
  it('reads client credentials from the stored row', () => {
    expect(
      authTypeOf({ auth_type: ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS })
    ).toBe(ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS);
  });

  it('treats a missing auth type as bearer', () => {
    expect(authTypeOf({ auth_type: null })).toBe(
      ENDPOINT_AUTH_TYPES.BEARER_TOKEN
    );
  });
});

describe('clientCredentialsFromEndpoint', () => {
  it('turns stored fields into form text and never fills the secret', () => {
    const draft = clientCredentialsFromEndpoint({
      token_url: 'https://auth.example.com/token',
      client_id: 'abc',
      scopes: ['read', 'write'],
      extra_payload: { resource: 'r' },
      has_client_secret: true,
    } as unknown as Endpoint);
    expect(draft.scopes).toBe('read write');
    expect(draft.client_secret).toBe('');
    expect(JSON.parse(draft.extra_payload)).toEqual({ resource: 'r' });
  });
});

describe('validateClientCredentials', () => {
  it('accepts a complete draft', () => {
    expect(validateClientCredentials(filled, false)).toBeNull();
  });

  it('requires a token URL, client ID and secret', () => {
    expect(
      validateClientCredentials({ ...filled, token_url: '' }, false)
    ).toMatch(/token url/i);
    expect(
      validateClientCredentials({ ...filled, token_url: 'nope' }, false)
    ).toMatch(/valid token url/i);
    expect(
      validateClientCredentials({ ...filled, client_id: ' ' }, false)
    ).toMatch(/client id/i);
    expect(
      validateClientCredentials({ ...filled, client_secret: '' }, false)
    ).toMatch(/client secret/i);
  });

  it('accepts an empty secret when one is stored', () => {
    expect(
      validateClientCredentials({ ...filled, client_secret: '' }, true)
    ).toBeNull();
  });
});

describe('parseExtraPayload', () => {
  it('returns null for empty text', () => {
    expect(parseExtraPayload('  ')).toEqual({ value: null });
  });

  it('rejects non-object and non-string values', () => {
    expect(parseExtraPayload('[1]')).toHaveProperty('error');
    expect(parseExtraPayload('{"a": 1}')).toHaveProperty('error');
    expect(parseExtraPayload('{')).toHaveProperty('error');
  });
});

describe('authPayload', () => {
  it('sends only the auth type for bearer', () => {
    expect(authPayload(ENDPOINT_AUTH_TYPES.BEARER_TOKEN, filled)).toEqual({
      auth_type: ENDPOINT_AUTH_TYPES.BEARER_TOKEN,
    });
  });

  it('clears empty optional fields and splits scopes', () => {
    expect(
      authPayload(ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS, {
        ...filled,
        scopes: ' read  write ',
      })
    ).toEqual({
      auth_type: ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS,
      token_url: filled.token_url,
      client_id: filled.client_id,
      client_secret: 'secret',
      audience: null,
      scopes: ['read', 'write'],
      extra_payload: null,
    });
  });

  it('leaves out an untouched secret', () => {
    const payload = authPayload(ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS, {
      ...filled,
      client_secret: '',
    });
    expect(payload).not.toHaveProperty('client_secret');
  });
});

describe('testAuthFields', () => {
  it('sends the bearer token for bearer', () => {
    expect(
      testAuthFields(ENDPOINT_AUTH_TYPES.BEARER_TOKEN, 'tok', filled)
    ).toEqual({
      auth_type: ENDPOINT_AUTH_TYPES.BEARER_TOKEN,
      auth_token: 'tok',
    });
  });

  it('sends the OAuth fields and no bearer token for client credentials', () => {
    const fields = testAuthFields(
      ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS,
      'tok',
      filled
    );
    expect(fields.client_secret).toBe('secret');
    expect(fields).not.toHaveProperty('auth_token');
  });
});
