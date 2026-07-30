export interface Token {
  id: string;
  name: string;
  token_obfuscated: string;
  expires_at: string;
  last_used_at?: string;
}

export interface TokenResponse {
  access_token: string;
  expires_at: string;
  name?: string;
}
