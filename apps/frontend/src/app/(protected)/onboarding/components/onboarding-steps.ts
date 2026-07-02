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
      'Invite up to 10 colleagues during onboarding to join your organization. You can skip this step and add team members later.',
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
    sidebarSubtitle: 'How to get started within a few minutes',
    contentTitle: 'Welcome to Rhesis!',
    contentDescription: 'Let us show you how to get started.',
    icon: RocketLaunchOutlinedIcon,
  },
];

export const ONBOARDING_STEP_COUNT = ONBOARDING_STEPS.length;
