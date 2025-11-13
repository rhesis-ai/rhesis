import { DriveStep } from 'driver.js';

/**
 * Tour for creating a project
 */
export const projectTourSteps: DriveStep[] = [
  {
    element: '[data-tour="create-project-button"]',
    popover: {
      title: 'Create Your First Project',
      description:
        'Projects help you organize your AI testing work. Click here to create your first project.',
      side: 'left',
      align: 'start',
    },
  },
];

/**
 * Tour for setting up an endpoint
 */
export const endpointTourSteps: DriveStep[] = [
  {
    element: '[data-tour="create-endpoint-button"]',
    popover: {
      title: 'Set Up an Endpoint',
      description:
        "Endpoints are the AI services you want to test. Let's create your first endpoint to get started.",
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="import-swagger-button"]',
    popover: {
      title: 'Import from Swagger',
      description:
        "You can quickly import endpoints from a Swagger/OpenAPI spec, or create them manually using the 'New Endpoint' button.",
      side: 'left',
      align: 'start',
    },
  },
];

/**
 * Tour for inviting users
 */
export const inviteUsersTourSteps: DriveStep[] = [
  {
    element: '[data-tour="invite-email-input"]',
    popover: {
      title: 'Invite Your Team',
      description:
        "Enter your team members' email addresses here. You can invite multiple people at once.",
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="send-invites-button"]',
    popover: {
      title: 'Send Invitations',
      description: 'Click here to send invitation emails to your team members.',
      side: 'left',
      align: 'start',
    },
  },
];

/**
 * Tour for creating test cases
 */
export const testCasesTourSteps: DriveStep[] = [
  {
    element: '[data-tour="create-test-button"]',
    popover: {
      title: 'Create Your First Test Cases',
      description:
        'Test cases define what to test in your AI endpoints. Click this button to see your options.',
      side: 'left',
      align: 'start',
      // onNextClick handler is added dynamically in OnboardingContext
    },
  },
  {
    element: '[data-tour="test-generation-modal"]',
    popover: {
      title: 'Choose Your Method',
      description:
        'You can create tests manually, generate them with AI, or import them. Pick the method that works best for you!',
      side: 'top',
      align: 'center',
      // Don't specify showButtons - let driver.js automatically show correct buttons for last step
    },
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
  showButtons: ['next', 'previous', 'close'],
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
export function getTourSteps(tourId: string): DriveStep[] {
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
