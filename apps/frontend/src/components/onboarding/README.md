# Onboarding Tour System

An interactive onboarding system built with driver.js to guide new users through the Rhesis platform.

## Overview

The onboarding system consists of:

- **Floating Checklist Widget**: A collapsible widget that appears in the bottom-right corner on all protected pages
- **Dashboard Card**: A larger, more prominent card that displays on the dashboard
- **Multi-page Tours**: Guided tours that highlight key UI elements across different pages
- **Progress Tracking**: LocalStorage-based persistence to track user progress

## Architecture

### Core Components

#### 1. Context & State Management

- **`OnboardingContext`**: React context that manages onboarding state globally
- **`onboarding-service.ts`**: Utility functions for localStorage operations and progress calculations
- **`onboarding-tours.ts`**: Tour configurations with driver.js steps

#### 2. UI Components

- **`OnboardingChecklist`**: Floating widget (bottom-right corner)
- **`OnboardingDashboardCard`**: Dashboard card variant

#### 3. Hooks

- **`useOnboarding()`**: Access onboarding state and actions
- **`useOnboardingTour(tourId)`**: Enable tour auto-start on specific pages

## Onboarding Flow

The system guides users through 4 key steps:

1. **Create Project** (`/projects`)
   - Tour highlights the "Create Project" button
   - Marks complete when user has at least one project

2. **Setup Endpoint** (`/endpoints`)
   - Tour shows "New Endpoint" button and creation options
   - Marks complete when user has at least one endpoint

3. **Invite Team Members** (`/organizations/team`)
   - Tour points to email input and send button
   - Marks complete when user has invited at least one team member

4. **Create Test Cases** (`/tests`)
   - Tour demonstrates the "Add Tests" button
   - Marks complete when user has created at least one test

## Usage

### Integrating a New Tour

1. **Add tour configuration** in `config/onboarding-tours.ts`:

```typescript
export const myTourSteps: DriveStep[] = [
  {
    element: '[data-tour="my-element"]',
    popover: {
      title: 'My Step Title',
      description: 'Description of this step',
      side: 'bottom',
      align: 'start',
    },
  },
];
```

2. **Add data-tour attributes** to target elements:

```tsx
<Button data-tour="my-element">Click Me</Button>
```

3. **Enable tour on the page**:

```tsx
import { useOnboardingTour } from '@/hooks/useOnboardingTour';

function MyPage() {
  useOnboardingTour('myTour'); // Auto-starts if URL has ?tour=myTour

  // ... rest of component
}
```

4. **Mark step complete** when action is done:

```tsx
import { useOnboarding } from '@/contexts/OnboardingContext';

function MyPage() {
  const { markStepComplete } = useOnboarding();

  useEffect(() => {
    if (userCompletedAction) {
      markStepComplete('myStepId');
    }
  }, [userCompletedAction]);
}
```

### Adding a New Checklist Step

1. Update `OnboardingProgress` interface in `types/onboarding.ts`
2. Add step to `ONBOARDING_STEPS` array in both:
   - `components/onboarding/OnboardingChecklist.tsx`
   - `components/onboarding/OnboardingDashboardCard.tsx`
3. Update completion logic in `utils/onboarding-service.ts`

## State Management

### Progress State Shape

```typescript
{
  projectCreated: boolean;
  endpointSetup: boolean;
  usersInvited: boolean;
  testCasesCreated: boolean;
  dismissed: boolean;
  lastUpdated: number;
}
```

### LocalStorage Key

`rhesis_onboarding_progress`

## API

### `useOnboarding()` Hook

```typescript
const {
  progress, // Current progress state
  isComplete, // Whether all required steps are done
  completionPercentage, // 0-100 percentage
  markStepComplete, // (stepId) => void
  dismissOnboarding, // () => void
  resetOnboarding, // () => void
  startTour, // (tourId) => void
  activeTour, // Current active tour ID or null
} = useOnboarding();
```

### `useOnboardingTour(tourId)` Hook

```typescript
// Auto-starts tour if ?tour=tourId in URL
useOnboardingTour('project');
```

## Styling

Custom styles are in `styles/OnboardingTour.module.css` and override driver.js defaults to match Material-UI theme.

## Tour Navigation

Tours are triggered by:

1. **Clicking checklist items**: Navigates to page with `?tour=tourId` param
2. **URL param**: Any page with `?tour=tourId` auto-starts that tour
3. **Manual**: Call `startTour(tourId)` from `useOnboarding()` hook

## Best Practices

1. **Keep tours short**: 2-3 steps maximum per tour
2. **Use descriptive data-tour attributes**: e.g., `data-tour="create-project-button"`
3. **Mark complete on action, not navigation**: Wait for actual user action
4. **Make optional steps clear**: Use `optional: true` flag
5. **Test across viewports**: Tours should work on mobile too

## Future Enhancements

Potential improvements:

- Backend persistence (sync across devices)
- A/B testing different tour flows
- Analytics tracking (which steps users skip, etc.)
- Video tutorials embedded in tours
- Contextual help tooltips outside of tours
