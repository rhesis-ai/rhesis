# Routing

This document explains the routing system used in the Rhesis frontend application, which is built with Next.js App Router.

## App Router Overview

The Rhesis frontend uses Next.js App Router, which provides a file-system based routing approach where:

- Folders define routes
- Files define UI
- Special files handle specific functionality (layout, page, loading, etc.)
- Dynamic segments are supported with brackets notation

## Route Structure

The main route structure is organized as follows:

```
src/app/
├── (protected)/            # Route group for authenticated pages
│   ├── dashboard/          # Dashboard route
│   │   └── page.tsx        # Dashboard page component
│   ├── projects/           # Projects route
│   │   ├── [id]/           # Dynamic project route
│   │   │   └── page.tsx    # Project detail page
│   │   └── page.tsx        # Projects list page
│   ├── tests/              # Tests route
│   │   ├── [id]/           # Dynamic test route
│   │   │   └── page.tsx    # Test detail page
│   │   └── page.tsx        # Tests list page
│   └── layout.tsx          # Protected layout with auth check
├── api/                    # API routes
│   └── [...]/              # API endpoints
├── auth/                   # Authentication routes
│   ├── login/              # Login route
│   │   └── page.tsx        # Login page
│   ├── register/           # Register route
│   │   └── page.tsx        # Register page
│   └── layout.tsx          # Auth layout
├── layout.tsx              # Root layout
└── page.tsx                # Home page
```

## Route Groups

Route groups are used to organize routes without affecting the URL structure. In our application, we use route groups for:

- `(protected)`: Pages that require authentication
- `(public)`: Pages that are publicly accessible

## Layouts

Layouts are used to share UI between multiple pages. Our application uses several levels of layouts:

1. **Root Layout (`app/layout.tsx`)**: Applied to all pages, contains:
   - Theme provider
   - Global styles
   - Top-level metadata

2. **Auth Layout (`app/auth/layout.tsx`)**: Applied to authentication pages, contains:
   - Centered card layout
   - Brand elements
   - No navigation

3. **Protected Layout (`app/(protected)/layout.tsx`)**: Applied to authenticated pages, contains:
   - Authentication check
   - Main navigation (sidebar)
   - Header
   - User menu

## Navigation

### Link Component

For client-side navigation, use the Next.js `Link` component:

```tsx
import Link from 'next/link';

<Link href="/projects">Projects</Link>
```

### Programmatic Navigation

For programmatic navigation, use the `useRouter` hook:

```tsx
import { useRouter } from 'next/navigation';

const router = useRouter();
router.push('/projects');
```

## Route Protection

Routes under the `(protected)` route group are protected by authentication middleware:

1. **Middleware Check**: The `middleware.ts` file checks for authentication on protected routes
2. **Session Validation**: If no valid session exists, the user is redirected to the login page
3. **Role-Based Access**: Some routes may have additional role-based access controls

## Dynamic Routes

Dynamic routes use parameters in the URL, defined with brackets notation:

- `/projects/[id]`: Project detail page, where `[id]` is the project identifier
- `/tests/[id]`: Test detail page, where `[id]` is the test identifier

Access parameters in the page component:

```tsx
// app/(protected)/projects/[id]/page.tsx
export default function ProjectPage({ params }: { params: { id: string } }) {
  const { id } = params;
  // Use the ID to fetch project data
  return <div>Project {id}</div>;
}
```

## Loading States

Loading states are defined using special `loading.tsx` files:

```tsx
// app/(protected)/projects/loading.tsx
export default function Loading() {
  return <div>Loading projects...</div>;
}
```

## Error Handling

Error states are defined using special `error.tsx` files:

```tsx
// app/(protected)/projects/error.tsx
'use client';

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

## Not Found Pages

Not found pages are defined using special `not-found.tsx` files:

```tsx
// app/(protected)/projects/[id]/not-found.tsx
export default function NotFound() {
  return <div>Project not found</div>;
}
```

## Metadata

Page metadata is defined using the `metadata` export:

```tsx
// app/(protected)/projects/page.tsx
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Projects | Rhesis',
  description: 'Manage your Rhesis projects',
};

export default function ProjectsPage() {
  // ...
}
```

## Best Practices

1. **Keep Pages Thin**: Page components should focus on data fetching and layout, with most UI logic in components
2. **Use Server Components**: Leverage server components for data fetching where possible
3. **Client Components**: Use the `'use client'` directive only when needed for interactivity
4. **Parallel Routes**: Use parallel routes for complex layouts with independent navigation
5. **Intercepting Routes**: Use intercepting routes for modals and overlays 