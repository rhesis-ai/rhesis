import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import PersonAddOutlinedIcon from '@mui/icons-material/PersonAddOutlined';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import type { SvgIconComponent } from '@mui/icons-material';

export interface OnboardingStepConfig {
  id: string;
  sidebarTitle: string;
  sidebarSubtitle: string;
  contentTitle: string;
  contentDescription: string;
  icon: SvgIconComponent;
}

export const ONBOARDING_STEPS: OnboardingStepConfig[] = [
  {
    id: 'organization-details',
    sidebarTitle: 'Organization Details',
    sidebarSubtitle: 'Provide organization details',
    contentTitle: 'Create your workplace',
    contentDescription:
      'Provide us with a few details to personalize your experience.',
    icon: InfoOutlinedIcon,
  },
  {
    id: 'invite-team',
    sidebarTitle: 'Invite your team',
    sidebarSubtitle: 'Start collaborating with your team',
    contentTitle: 'Invite your team',
    contentDescription:
      'Invite colleagues to join your organization. You can skip this step and add team members later.',
    icon: PersonAddOutlinedIcon,
  },
  {
    id: 'review',
    sidebarTitle: 'Review your details',
    sidebarSubtitle: 'Review your information',
    contentTitle: 'Review your details',
    contentDescription:
      'Please have a look at your details again before completing setup.',
    icon: SearchOutlinedIcon,
  },
  {
    id: 'welcome',
    sidebarTitle: 'Welcome to Rhesis!',
    sidebarSubtitle: 'See how Rhesis works in 5 minutes',
    contentTitle: 'Welcome to Rhesis!',
    contentDescription:
      'A 5-minute look at how engineers and domain experts test AI agents together. Watch it now, or finish setup and dive in.',
    icon: RocketLaunchOutlinedIcon,
  },
];

/** The welcome step is only there when the deployment configured a video. */
export function getOnboardingSteps(hasVideo: boolean): OnboardingStepConfig[] {
  return hasVideo
    ? ONBOARDING_STEPS
    : ONBOARDING_STEPS.filter(step => step.id !== 'welcome');
}

export type OnboardingStatus =
  | 'idle'
  | 'creating_organization'
  | 'updating_user'
  | 'loading_initial_data'
  | 'creating_project'
  | 'completed';

/** Label of the button that finishes setup, following its progress. */
export function finishButtonLabel(status: OnboardingStatus): string {
  switch (status) {
    case 'creating_organization':
      return 'Creating organization...';
    case 'updating_user':
      return 'Updating user information...';
    case 'loading_initial_data':
      return 'Loading initial data...';
    case 'creating_project':
      return 'Creating your project...';
    case 'completed':
      return 'Setup complete. Redirecting...';
    default:
      return 'Finish up';
  }
}
