import { UUID } from 'crypto';

export interface Organization {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  website?: string;
  logo_url?: string;
  email?: string;
  phone?: string;
  address?: string;
  is_active?: boolean;
  max_users?: number;
  subscription_ends_at?: string;
  domain?: string;
  is_domain_verified?: boolean;
  createdAt: string;
  owner_id: UUID;
  user_id: UUID;
}

export interface SSOConfig {
  enabled: boolean;
  provider_type: string;
  issuer_url: string;
  client_id: string;
  client_secret?: string;
  scopes: string;
  auto_provision_users: boolean;
  allowed_domains?: string[] | null;
  allowed_auth_methods?: string[] | null;
  slug?: string;
  login_url?: string;
}

export interface SSOTestResult {
  success: boolean;
  message: string;
}
