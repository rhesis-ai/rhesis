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

| Step           | ID                 | Page                  | Required |
| -------------- | ------------------ | --------------------- | -------- |
| Create Project | `projectCreated`   | `/projects`           | ✅ Yes   |
| Setup Endpoint | `endpointSetup`    | `/endpoints`          | ✅ Yes   |
| Invite Team    | `usersInvited`     | `/organizations/team` | ✅ Yes   |
| Create Tests   | `testCasesCreated` | `/tests`              | ✅ Yes   |

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

## ⚠️ Important: Overriding Navigation Callbacks

**Critical Rule:** When you override `onNextClick` or `onPrevClick`, you take full control of navigation. According to [driver.js documentation](https://driverjs.com/docs/configuration):

> By overriding `onNextClick`, you control the navigation of the driver. You MUST call `driverObj.moveNext()`, `driverObj.movePrevious()`, or `driverObj.destroy()` explicitly.

### Best Practices:

1. **Avoid global `onNextClick`/`onPrevClick` overrides** - Let driver.js handle default navigation
2. **Only override at step-level when absolutely necessary** - For example, to trigger an action before advancing
3. **Always call a driver method** - Either `moveNext()`, `movePrevious()`, or `destroy()`
4. **Don't rely on external code to call driver methods** - Keep all navigation logic in the step callbacks
5. **Use appropriate hooks for side effects** - Use `onHighlighted`, `onDeselected`, etc. for non-navigation logic

### Example: Proper Step-Level Override

```typescript
{
  element: '[data-tour="my-button"]',
  popover: {
    title: 'Click to Continue',
    onNextClick: (element) => {
      // Perform custom action (e.g., click the button)
      if (element) {
        (element as HTMLElement).click();
      }

      // CRITICAL: You MUST call a driver method
      // Wait for async operation if needed, then advance
      setTimeout(() => {
        driverInstance.moveNext();
      }, 300);
    },
  },
}
```

### Common Mistakes to Avoid:

❌ **Bad:** Overriding `onNextClick` without calling a driver method

```typescript
onNextClick: element => {
  element.click(); // No driver method call!
};
```

❌ **Bad:** Relying on external code to handle navigation

```typescript
onNextClick: element => {
  element.click();
  // Hoping some other code will call moveNext() - DON'T DO THIS
};
```

✅ **Good:** Complete navigation handling in the callback

```typescript
onNextClick: element => {
  element.click();
  setTimeout(() => driverInstance.moveNext(), 300); // ✓ Proper navigation
};
```

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
