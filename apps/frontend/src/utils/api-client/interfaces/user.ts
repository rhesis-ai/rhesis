import type { Currency } from '@/utils/money';
import type { JobRole, ReferralSource } from '@/constants/user-profile';
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
  /** Set for invitees, who skip /onboarding and get the profile questions in a dialog. */
  profile_survey_pending?: boolean;
  last_updated?: string;
}

/**
 * Onboarding steps computed by the backend from real data (GET
 * /users/onboarding-status). Rows seeded as the example project never count.
 */
export interface OnboardingStatus {
  project_created: boolean;
  endpoint_setup: boolean;
  users_invited: boolean;
  test_cases_created: boolean;
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

/** How this user wants things shown. The backend has carried language,
 *  timezone and the date formats here for a while; only currency is read. */
export interface LocalizationSettings {
  language?: string | null;
  timezone?: string | null;
  date_format?: string | null;
  time_format?: string | null;
  /** Unset defers to the organization's currency, then to USD. */
  currency?: Currency | null;
}

export interface UserSettings extends WithPermittedActions {
  models?: ModelsSettings;
  localization?: LocalizationSettings;
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
  localization?: LocalizationSettings;
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
  job_role?: JobRole;
  job_role_other?: string;
  referral_source?: ReferralSource;
  referral_source_other?: string;
}
