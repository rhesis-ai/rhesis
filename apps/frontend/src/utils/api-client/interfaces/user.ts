import { UUID } from 'crypto';

// User Settings Interfaces
export interface LLMModelSettings {
  model_id?: UUID;
}

export interface ModelsSettings {
  generation?: LLMModelSettings;
  evaluation?: LLMModelSettings;
  execution?: LLMModelSettings;
  embedding?: LLMModelSettings;
}

export interface OnboardingProgress {
  project_created?: boolean;
  endpoint_setup?: boolean;
  users_invited?: boolean;
  test_cases_created?: boolean;
  dismissed?: boolean;
  last_updated?: string;
}

import type { WithPermittedActions } from '@/types/affordances';

/**
 * Email notification preferences. Undefined means the user never touched the
 * setting, which the backend reads as on.
 */
export interface EmailNotificationSettings {
  job_completion?: boolean;
  task_assignment?: boolean;
}

export interface NotificationSettings {
  email?: EmailNotificationSettings;
}

export interface PolyphemusAccess {
  revoked_at?: string;
  requested_at?: string;
}

export interface DefaultProjectSetting {
  project_id: UUID;
  name: string;
}

export interface UserSettings extends WithPermittedActions {
  models?: ModelsSettings;
  notifications?: NotificationSettings;
  onboarding?: OnboardingProgress;
  polyphemus_access?: PolyphemusAccess;
  default_project?: DefaultProjectSetting;
  is_verified?: boolean;
  has_password: boolean;
  provider_type?: string;
  email: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
}

export interface UserSettingsUpdate {
  models?: ModelsSettings;
  notifications?: NotificationSettings;
  onboarding?: OnboardingProgress;
  default_project?: DefaultProjectSetting;
}

// User Interfaces
export interface User {
  id: UUID;
  email: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
  is_active?: boolean;
  is_verified?: boolean;
  organization_id?: UUID;
  joined_at?: string | null;
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
