/**
 * Options for the onboarding profile questions. Keys mirror the backend's
 * `app/constants_user_profile.py` (`JobRole`, `ReferralSource`); keep both in sync.
 */

import type { OnboardingProfile } from '@/utils/api-client/interfaces/user';

export type JobRole =
  | 'engineer'
  | 'data_scientist'
  | 'qa'
  | 'product_manager'
  | 'domain_expert'
  | 'compliance_risk'
  | 'leadership'
  | 'researcher'
  | 'student'
  | 'other';

export type ReferralSource =
  | 'google_search'
  | 'ai_assistant'
  | 'github'
  | 'linkedin'
  | 'friend_colleague'
  | 'event_conference'
  | 'blog_article'
  | 'other';

export const JOB_ROLE_OPTIONS: { value: JobRole; label: string }[] = [
  { value: 'engineer', label: 'Engineer' },
  { value: 'data_scientist', label: 'Data Scientist' },
  { value: 'qa', label: 'QA / Testing' },
  { value: 'product_manager', label: 'Product Manager' },
  { value: 'domain_expert', label: 'Domain Expert' },
  { value: 'compliance_risk', label: 'Compliance / Risk' },
  { value: 'leadership', label: 'Leadership' },
  { value: 'researcher', label: 'Researcher' },
  { value: 'student', label: 'Student' },
  { value: 'other', label: 'Other' },
];

export const REFERRAL_SOURCE_OPTIONS: {
  value: ReferralSource;
  label: string;
}[] = [
  { value: 'google_search', label: 'Google search' },
  { value: 'ai_assistant', label: 'AI assistant (ChatGPT, Claude, ...)' },
  { value: 'github', label: 'GitHub' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'friend_colleague', label: 'Friend or colleague' },
  { value: 'event_conference', label: 'Event or conference' },
  { value: 'blog_article', label: 'Blog or article' },
  { value: 'other', label: 'Other' },
];

export interface ProfileAnswers {
  jobRole: JobRole | '';
  jobRoleOther: string;
  referralSource: ReferralSource | '';
  referralSourceOther: string;
}

export const EMPTY_PROFILE_ANSWERS: ProfileAnswers = {
  jobRole: '',
  jobRoleOther: '',
  referralSource: '',
  referralSourceOther: '',
};

/**
 * The answers as `onboarding.profile` settings. Unanswered fields are sent as
 * `null` so a settings merge clears what an earlier answer left behind.
 */
export function toProfileUpdate(answers: ProfileAnswers): OnboardingProfile {
  return {
    job_role: answers.jobRole || null,
    job_role_other:
      answers.jobRole === 'other' ? answers.jobRoleOther.trim() || null : null,
    referral_source: answers.referralSource || null,
    referral_source_other:
      answers.referralSource === 'other'
        ? answers.referralSourceOther.trim() || null
        : null,
  };
}

export function labelForJobRole(answers: ProfileAnswers): string {
  if (answers.jobRole === 'other' && answers.jobRoleOther.trim()) {
    return answers.jobRoleOther.trim();
  }
  return JOB_ROLE_OPTIONS.find(o => o.value === answers.jobRole)?.label ?? '';
}

export function labelForReferralSource(answers: ProfileAnswers): string {
  if (
    answers.referralSource === 'other' &&
    answers.referralSourceOther.trim()
  ) {
    return answers.referralSourceOther.trim();
  }
  return (
    REFERRAL_SOURCE_OPTIONS.find(o => o.value === answers.referralSource)
      ?.label ?? ''
  );
}
