import { UUID } from 'crypto';

// User Settings Interfaces
export interface LLMModelSettings {
  model_id?: UUID;
  fallback_model_id?: UUID;
  temperature?: number;
  max_tokens?: number;
}

export interface ModelsSettings {
  generation?: LLMModelSettings;
  evaluation?: LLMModelSettings;
}

export interface UISettings {
  theme?: 'light' | 'dark' | 'auto';
  density?: 'compact' | 'comfortable' | 'spacious';
  sidebar_collapsed?: boolean;
  default_page_size?: number;
}

export interface EmailNotificationSettings {
  test_run_complete?: boolean;
  test_failures?: boolean;
  weekly_summary?: boolean;
}

export interface InAppNotificationSettings {
  test_run_complete?: boolean;
  mentions?: boolean;
}

export interface NotificationSettings {
  email?: EmailNotificationSettings;
  in_app?: InAppNotificationSettings;
}

export interface LocalizationSettings {
  language?: string;
  timezone?: string;
  date_format?: string;
  time_format?: '12h' | '24h';
}

export interface PrivacySettings {
  show_email?: boolean;
  show_activity?: boolean;
}

export interface OnboardingProgress {
  project_created?: boolean;
  endpoint_setup?: boolean;
  users_invited?: boolean;
  test_cases_created?: boolean;
  dismissed?: boolean;
  last_updated?: string;
}

export interface UserSettings {
  version: number;
  models?: ModelsSettings;
  ui?: UISettings;
  notifications?: NotificationSettings;
  localization?: LocalizationSettings;
  privacy?: PrivacySettings;
  onboarding?: OnboardingProgress;
}

export interface UserSettingsUpdate {
  models?: ModelsSettings;
  ui?: UISettings;
  notifications?: NotificationSettings;
  localization?: LocalizationSettings;
  privacy?: PrivacySettings;
  onboarding?: OnboardingProgress;
}

// User Interfaces
export interface User {
  id: UUID;
  email: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  auth0_id?: string;
  picture?: string;
  is_active?: boolean;
  organization_id?: UUID;
  user_settings?: UserSettings;
}

export interface UserCreate {
  email: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  auth0_id?: string;
  picture?: string;
  is_active?: boolean;
  organization_id?: UUID;
  send_invite?: boolean;
}

export interface UserUpdate {
  email?: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  auth0_id?: string;
  picture?: string;
  is_active?: boolean;
  organization_id?: UUID;
}
