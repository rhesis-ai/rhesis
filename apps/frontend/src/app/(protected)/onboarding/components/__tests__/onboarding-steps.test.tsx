import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { finishButtonLabel, getOnboardingSteps } from '../onboarding-steps';
import FinishStep from '../FinishStep';
import OnboardingProgressBar from '../OnboardingProgressBar';

const formData = {
  firstName: 'Ada',
  lastName: 'Lovelace',
  organizationName: 'Acme',
  projectName: 'Agents',
  website: '',
  invites: [],
} as unknown as React.ComponentProps<typeof FinishStep>['formData'];

describe('onboarding steps', () => {
  it('includes the welcome step only when a video is configured', () => {
    expect(getOnboardingSteps(true).map(s => s.id)).toEqual([
      'organization-details',
      'invite-team',
      'review',
      'welcome',
    ]);
    expect(getOnboardingSteps(false).map(s => s.id)).toEqual([
      'organization-details',
      'invite-team',
      'review',
    ]);
  });

  it('draws one progress segment per step', () => {
    const { container } = render(
      <OnboardingProgressBar activeStep={0} steps={getOnboardingSteps(false)} />
    );
    expect(container.firstElementChild?.children).toHaveLength(3);
  });

  it('labels the finish button with the setup progress', () => {
    expect(finishButtonLabel('idle')).toBe('Finish up');
    expect(finishButtonLabel('creating_project')).toBe(
      'Creating your project...'
    );
  });
});

describe('Review step as the last step', () => {
  it('finishes setup instead of moving on', () => {
    const onFinish = jest.fn();
    render(
      <FinishStep
        formData={formData}
        onNext={onFinish}
        onBack={jest.fn()}
        finishLabel="Finish up"
      />
    );

    expect(
      screen.queryByRole('button', { name: 'Next' })
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Finish up' }));
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it('says Next when the welcome video step follows', () => {
    render(
      <FinishStep formData={formData} onNext={jest.fn()} onBack={jest.fn()} />
    );
    expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument();
  });
});
