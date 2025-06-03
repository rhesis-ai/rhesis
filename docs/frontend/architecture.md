# Architecture Overview

This document provides a high-level overview of the Rhesis frontend architecture.

## Tech Stack

* **Framework:** [Next.js](https://nextjs.org/) 15.3.0 with App Router
* **Language:** [TypeScript](https://www.typescriptlang.org/) 5.8.3
* **UI:** [Material UI (MUI)](https://mui.com/) v6
* **Authentication:** [NextAuth.js](https://next-auth.js.org/) 5.0.0-beta.25
* **State Management:** React Context API
* **Styling:** MUI theming with Emotion
* **Data Visualization:** [Recharts](https://recharts.org/) 2.15.0
* **Data Grid:** MUI X Data Grid
* **Flow Visualization:** [React Flow](https://reactflow.dev/) 11.11.4
* **Code Editor:** [Monaco Editor](https://microsoft.github.io/monaco-editor/)
* **Icons:** MUI Icons, Lucide React
* **Date Handling:** date-fns, dayjs
* **React:** React 19

## Project Structure

The frontend codebase follows a modular architecture organized by feature and responsibility:

```
src/
├── app/                  # Next.js App Router with route groups
│   ├── (protected)/      # Authentication-protected routes
│   ├── api/              # API routes
│   ├── auth/             # Authentication pages
│   └── ...               # Other routes
├── components/           # Shared UI components
│   ├── common/           # Reusable components (charts, tables, etc.)
│   ├── layout/           # Layout components
│   ├── navigation/       # Navigation components
│   ├── providers/        # Context providers
│   ├── auth/             # Authentication components
│   └── ...               # Feature-specific components
├── utils/                # Utility functions and services
│   ├── api-client/       # API client implementation with typed interfaces
│   └── ...               # Other utilities
├── actions/              # Server actions
├── types/                # TypeScript type definitions
├── styles/               # Theme configuration
└── constants/            # Application constants
```

## Key Architectural Patterns

### App Router

The application uses Next.js App Router for routing, which provides:
- File-based routing
- Route groups for organization
- Layout nesting
- Server components
- Client components where needed
- Route protection with middleware

### Component Architecture

Components follow these principles:
- **Atomic Design:** Building from small, reusable components to complex page layouts
- **Component Composition:** Favoring composition over inheritance
- **Separation of Concerns:** UI components are separate from data fetching and business logic
- **Typed Props:** All components have well-defined TypeScript interfaces

### Data Flow

The application follows these data flow patterns:
- **Server Components:** Fetch data on the server when possible
- **React Context:** For global state management
- **Server Actions:** For mutations and form submissions
- **API Client:** Type-safe API integration

### Authentication

Authentication is handled by NextAuth.js with:
- Route protection via middleware
- Session management
- Multiple authentication providers (Google, etc.)
- Role-based access control

### Styling Approach

The styling system uses:
- MUI's theming system
- Emotion for CSS-in-JS
- Responsive design principles
- Design tokens for consistent styling

## Performance Considerations

- Server components for improved initial load times
- Client components only where interactivity is required
- Image optimization with Next.js Image component
- Route prefetching
- Code splitting 