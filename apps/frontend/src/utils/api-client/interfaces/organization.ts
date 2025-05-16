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