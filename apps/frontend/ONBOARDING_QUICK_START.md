# Onboarding System Quick Start

## 🎯 For Developers: Adding a New Tour

### 1. Define Tour Steps

Add to `src/config/onboarding-tours.ts`:

```typescript
export const myNewTourSteps: DriveStep[] = [
  {
    element: '[data-tour="my-button"]',
    popover: {
      title: 'Step Title',
      description: 'What this does...',
      side: 'bottom', // top | right | bottom | left
      align: 'start', // start | center | end
    },
  },
];

// Add to getTourSteps function:
case 'myNewTour':
  return myNewTourSteps;
```

### 2. Add Data Attributes

```tsx
<Button data-tour="my-button">Click Me</Button>
```

### 3. Enable Tour on Page

```tsx
import { useOnboardingTour } from '@/hooks/useOnboardingTour';

export default function MyPage() {
  useOnboardingTour('myNewTour');
  // ...
}
```

### 4. Track Completion

```tsx
import { useOnboarding } from '@/contexts/OnboardingContext';

const { markStepComplete } = useOnboarding();

useEffect(() => {
  if (userDidTheAction) {
    markStepComplete('myStepId');
  }
}, [userDidTheAction]);
```

## 🧪 For Testing

### Reset Onboarding (Chrome DevTools)

```javascript
// Clear progress
localStorage.removeItem('rhesis_onboarding_progress');

// Or reset programmatically
const { resetOnboarding } = useOnboarding();
resetOnboarding();
```

### Test Tour URLs

```
/projects?tour=project
/endpoints?tour=endpoint
/organizations/team?tour=invite
/tests?tour=testCases
```

## 📋 Onboarding Checklist Items

| Step           | ID                 | Page                  | Required    |
| -------------- | ------------------ | --------------------- | ----------- |
| Create Project | `projectCreated`   | `/projects`           | ✅ Yes      |
| Setup Endpoint | `endpointSetup`    | `/endpoints`          | ✅ Yes      |
| Invite Team    | `usersInvited`     | `/organizations/team` | ⚠️ Optional |
| Create Tests   | `testCasesCreated` | `/tests`              | ✅ Yes      |

## 🎨 Styling Tours

Edit `src/styles/OnboardingTour.module.css`:

```css
:global(.driver-popover) {
  /* Customize popover */
}

:global(.driver-popover-next-btn) {
  /* Customize buttons */
}
```

## 🔧 Common Tasks

### Hide Checklist Widget

```tsx
const { dismissOnboarding } = useOnboarding();
dismissOnboarding();
```

### Check Progress

```tsx
const { progress, completionPercentage, isComplete } = useOnboarding();

console.log(progress);
// { projectCreated: true, endpointSetup: false, ... }

console.log(completionPercentage); // 0-100

console.log(isComplete); // true/false
```

### Manually Start Tour

```tsx
const { startTour } = useOnboarding();
startTour('project'); // Starts project tour
```

## 📦 File Structure

```
apps/frontend/src/
├── components/
│   └── onboarding/
│       ├── OnboardingChecklist.tsx       # Floating widget
│       ├── OnboardingDashboardCard.tsx   # Dashboard card
│       ├── index.ts                       # Exports
│       └── README.md                      # Full docs
├── contexts/
│   └── OnboardingContext.tsx             # State management
├── hooks/
│   └── useOnboardingTour.ts              # Auto-start hook
├── config/
│   └── onboarding-tours.ts               # Tour definitions
├── utils/
│   └── onboarding-service.ts             # LocalStorage utils
├── types/
│   └── onboarding.ts                     # TypeScript types
└── styles/
    └── OnboardingTour.module.css         # Custom styles
```

## 🐛 Troubleshooting

### "useOnboarding must be used within an OnboardingProvider" Error

This error occurs when a component using `useOnboarding()` is rendered before the context provider is ready. **Solution:**

Wrap the component in a client-side mount check:

```tsx
const [mounted, setMounted] = React.useState(false);

React.useEffect(() => {
  setMounted(true);
}, []);

// Only render after mount
{
  mounted && <OnboardingDashboardCard />;
}
```

### Tour Not Starting?

1. Check element has `data-tour` attribute
2. Verify tour ID matches in URL param
3. Ensure `useOnboardingTour()` is called
4. Check element is visible (not `display: none`)

### Progress Not Saving?

1. Check localStorage is enabled
2. Verify completion logic runs
3. Check browser console for errors

### Widget Not Showing?

1. User might have dismissed it
2. Onboarding might be 100% complete
3. Check if user is on protected route

## 💡 Tips

- Keep tours short (2-3 steps max)
- Test on mobile devices
- Use clear, concise copy
- Highlight important actions
- Don't block critical functionality
- Allow users to skip/dismiss

## 🔗 Resources

- [driver.js Documentation](https://driverjs.com/)
- [Full Implementation Docs](../ONBOARDING_IMPLEMENTATION.md)
- [Component README](./src/components/onboarding/README.md)
