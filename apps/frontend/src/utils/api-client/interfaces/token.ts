export interface Token {
  id: string;
  name: string;
  token_obfuscated: string;
  token_type: string;
  expires_at: string;
  last_used_at?: string;
  last_refreshed_at?: string;
  user_id: string;
  organization_id?: string;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_obfuscated: string;
  token_type: string;
  expires_at: string;
  name?: string;
} 