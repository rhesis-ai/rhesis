import { DriveStep } from 'driver.js';
import { OnboardingStep, OnboardingStepId } from '@/types/onboarding';

/**
 * Centralized onboarding steps configuration
 * Single source of truth for all onboarding checklist items
 */
export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'projectCreated',
    title: 'Create your first project',
    description: 'Organize your work by creating a project',
    targetPath: '/projects?tour=project',
    tourId: 'project',
  },
  {
    id: 'endpointSetup',
    title: 'Set up an endpoint',
    description: 'Connect to your AI service endpoint',
    targetPath: '/endpoints?tour=endpoint',
    tourId: 'endpoint',
    requiresProjects: true,
  },
  {
    id: 'testCasesCreated',
    title: 'Create your first test cases',
    description: 'Define what to test in your endpoints',
    targetPath: '/tests?tour=testCases',
    tourId: 'testCases',
  },
  {
    id: 'usersInvited',
    title: 'Invite team members',
    description: 'Collaborate with your team',
    optional: true,
    targetPath: '/organizations/team?tour=invite',
    tourId: 'invite',
  },
];

/**
 * Path that triggers collapsed state for onboarding checklist
 */
export const ONBOARDING_COLLAPSE_PATH = '/dashboard';

/**
 * Extended DriveStep with completion tracking
 */
interface DriveStepWithCompletion extends DriveStep {
  __markComplete?: OnboardingStepId;
}

/**
 * Tour for creating a project
 */
export const projectTourSteps: DriveStepWithCompletion[] = [
  {
    element: '[data-tour="create-project-button"]',
    popover: {
      title: 'Create Your First Project',
      description:
        'Projects help you organize your AI testing work. Use the tour controls below to continue.',
      side: 'left',
      align: 'start',
    },
    disableActiveInteraction: true,
  },
];

/**
 * Tour for setting up an endpoint
 */
export const endpointTourSteps: DriveStepWithCompletion[] = [
  {
    element: '[data-tour="create-endpoint-button"]',
    popover: {
      title: 'Set Up an Endpoint',
      description:
        "Endpoints are the AI services you want to test. Use the 'Next' button below to continue the tour.",
      side: 'left',
      align: 'start',
    },
    disableActiveInteraction: true,
  },
  {
    element: '[data-tour="import-swagger-button"]',
    popover: {
      title: 'Import from Swagger',
      description:
        "You can quickly import endpoints from a Swagger/OpenAPI spec, or create them manually. Click 'Got it!' below to finish and start creating endpoints.",
      side: 'left',
      align: 'start',
    },
    disableActiveInteraction: true,
    // Mark complete when this step is highlighted (last step)
    __markComplete: 'endpointSetup',
  },
];

/**
 * Tour for inviting users
 */
export const inviteUsersTourSteps: DriveStepWithCompletion[] = [
  {
    element: '[data-tour="invite-email-input"]',
    popover: {
      title: 'Invite Your Team',
      description:
        "Enter your team members' email addresses here. You can invite multiple people at once. Use the 'Next' button below to continue.",
      side: 'bottom',
      align: 'start',
    },
    disableActiveInteraction: true,
  },
  {
    element: '[data-tour="send-invites-button"]',
    popover: {
      title: 'Send Invitations',
      description:
        "This button sends invitation emails to your team members. Click 'Got it!' below to finish the tour.",
      side: 'left',
      align: 'start',
    },
    disableActiveInteraction: true,
  },
];

/**
 * Tour for creating test cases
 */
export const testCasesTourSteps: DriveStepWithCompletion[] = [
  {
    element: '[data-tour="create-test-button"]',
    popover: {
      title: 'Create Your First Test Cases',
      description:
        "Test cases define what to test in your AI endpoints. Click 'Next' below to continue - we'll open the creation dialog for you.",
      side: 'left',
      align: 'start',
      // onNextClick handler is added dynamically in OnboardingContext
    },
    // Don't disable interaction - we need to programmatically click this button
    disableActiveInteraction: false,
  },
  {
    element: '[data-tour="test-generation-modal"]',
    popover: {
      title: 'Choose Your Method',
      description:
        "You can create tests manually, generate them with AI, or import them. Click 'Got it!' below to finish the tour and start creating tests.",
      side: 'top',
      align: 'center',
      // Don't specify showButtons - let driver.js automatically show correct buttons for last step
    },
    disableActiveInteraction: true,
    // Mark complete when this step is highlighted (last step)
    __markComplete: 'testCasesCreated',
  },
];

/**
 * Common driver.js configuration options
 */
export const driverConfig = {
  showProgress: true,
  progressText: '{{current}} of {{total}}',
  nextBtnText: 'Next',
  prevBtnText: 'Back',
  doneBtnText: 'Got it!',
  showButtons: ['next', 'previous', 'close'] as (
    | 'next'
    | 'previous'
    | 'close'
  )[],
  allowClose: true,
  overlayClickNext: false,
  smoothScroll: true,
  animate: true,
  stagePadding: 10,
  stageRadius: 10,
  // Let driver.js handle destruction by default
  // Only override onDestroyed in OnboardingContext for cleanup logic
};

/**
 * Get tour steps by tour ID
 */
export function getTourSteps(tourId: string): DriveStepWithCompletion[] {
  switch (tourId) {
    case 'project':
      return projectTourSteps;
    case 'endpoint':
      return endpointTourSteps;
    case 'invite':
      return inviteUsersTourSteps;
    case 'testCases':
      return testCasesTourSteps;
    default:
      return [];
  }
}
