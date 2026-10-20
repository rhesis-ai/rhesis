import {
  EMPTY_PROFILE_ANSWERS,
  labelForJobRole,
  labelForReferralSource,
  toProfileUpdate,
} from '../user-profile';

describe('toProfileUpdate', () => {
  it('sends null for unanswered fields, so a merge clears old answers', () => {
    expect(toProfileUpdate(EMPTY_PROFILE_ANSWERS)).toEqual({
      job_role: null,
      job_role_other: null,
      referral_source: null,
      referral_source_other: null,
    });
  });

  it('drops "Other" text left over after switching to a listed option', () => {
    const update = toProfileUpdate({
      ...EMPTY_PROFILE_ANSWERS,
      jobRole: 'engineer',
      jobRoleOther: 'leftover',
    });
    expect(update.job_role).toBe('engineer');
    expect(update.job_role_other).toBeNull();
  });

  it('trims "Other" text', () => {
    const update = toProfileUpdate({
      ...EMPTY_PROFILE_ANSWERS,
      referralSource: 'other',
      referralSourceOther: '  a podcast  ',
    });
    expect(update.referral_source_other).toBe('a podcast');
  });
});

describe('labels', () => {
  it('uses the option label, or the "Other" text when given', () => {
    expect(labelForJobRole({ ...EMPTY_PROFILE_ANSWERS, jobRole: 'qa' })).toBe(
      'QA / Testing'
    );
    expect(
      labelForReferralSource({
        ...EMPTY_PROFILE_ANSWERS,
        referralSource: 'other',
        referralSourceOther: 'Podcast',
      })
    ).toBe('Podcast');
  });
});
