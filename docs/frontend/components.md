# Component Library

This document provides an overview of the reusable components available in the Rhesis frontend application.

## Component Organization

Components are organized in the following directory structure:

```
src/components/
├── common/           # Reusable components used across features
├── layout/           # Layout components (header, footer, etc.)
├── navigation/       # Navigation components (sidebar, navbar, etc.)
├── providers/        # Context providers
├── auth/             # Authentication components
└── [feature]/        # Feature-specific components
```

## Core Components

### Layout Components

#### `AppLayout`

The main application layout wrapper used for authenticated pages.

**Usage:**
```tsx
<AppLayout>
  <YourPageContent />
</AppLayout>
```

#### `AuthLayout`

Layout for authentication pages (login, register, etc.).

**Usage:**
```tsx
<AuthLayout>
  <LoginForm />
</AuthLayout>
```

### Navigation Components

#### `Sidebar`

Main navigation sidebar with collapsible sections.

**Props:**
- `isOpen`: boolean - Controls whether the sidebar is expanded or collapsed
- `onToggle`: () => void - Callback when the sidebar toggle button is clicked

#### `Navbar`

Top navigation bar with user menu, notifications, and search.

**Props:**
- `user`: User - Current user object
- `onSearch`: (query: string) => void - Search callback

### Data Display Components

#### `DataTable`

Reusable table component with sorting, filtering, and pagination.

**Props:**
- `columns`: Column[] - Column definitions
- `data`: any[] - Table data
- `pagination`: PaginationProps - Pagination configuration
- `onSort`: (field: string, direction: 'asc' | 'desc') => void - Sort callback
- `onFilter`: (filters: Record<string, any>) => void - Filter callback

#### `DataGrid`

Advanced data grid component using MUI X Data Grid.

**Props:**
- `rows`: any[] - Grid data
- `columns`: GridColDef[] - Column definitions
- `pageSize`: number - Number of rows per page
- `loading`: boolean - Loading state

#### `Card`

Wrapper component for content cards.

**Props:**
- `title`: string - Card title
- `subtitle`: string - Optional card subtitle
- `actions`: React.ReactNode - Optional action buttons/menu
- `children`: React.ReactNode - Card content

### Form Components

#### `TextField`

Enhanced text input component.

**Props:**
- `label`: string - Input label
- `value`: string - Input value
- `onChange`: (e: React.ChangeEvent<HTMLInputElement>) => void - Change handler
- `error`: string - Optional error message
- `helperText`: string - Optional helper text
- `...MuiTextFieldProps` - All MUI TextField props are supported

#### `Select`

Enhanced select component.

**Props:**
- `label`: string - Select label
- `options`: { label: string, value: string | number }[] - Select options
- `value`: string | number - Selected value
- `onChange`: (value: string | number) => void - Change handler
- `...MuiSelectProps` - All MUI Select props are supported

#### `Button`

Enhanced button component with variants.

**Props:**
- `variant`: 'primary' | 'secondary' | 'danger' | 'ghost' - Button variant
- `size`: 'small' | 'medium' | 'large' - Button size
- `loading`: boolean - Loading state
- `...MuiButtonProps` - All MUI Button props are supported

### Feedback Components

#### `Alert`

Component for displaying alerts and notifications.

**Props:**
- `severity`: 'success' | 'info' | 'warning' | 'error' - Alert type
- `title`: string - Alert title
- `message`: string - Alert message
- `onClose`: () => void - Close handler

#### `Dialog`

Modal dialog component.

**Props:**
- `open`: boolean - Controls dialog visibility
- `onClose`: () => void - Close handler
- `title`: string - Dialog title
- `actions`: React.ReactNode - Dialog action buttons
- `children`: React.ReactNode - Dialog content

### Visualization Components

#### `LineChart`

Line chart component using Recharts.

**Props:**
- `data`: any[] - Chart data
- `xKey`: string - X-axis data key
- `yKeys`: { key: string, name: string, color: string }[] - Y-axis data keys
- `height`: number - Chart height

#### `BarChart`

Bar chart component using Recharts.

**Props:**
- `data`: any[] - Chart data
- `xKey`: string - X-axis data key
- `yKeys`: { key: string, name: string, color: string }[] - Y-axis data keys
- `height`: number - Chart height

#### `FlowChart`

Interactive flow chart using React Flow.

**Props:**
- `nodes`: Node[] - Flow nodes
- `edges`: Edge[] - Flow edges
- `onNodesChange`: (changes: NodeChange[]) => void - Node change handler
- `onEdgesChange`: (changes: EdgeChange[]) => void - Edge change handler

## Using Components

When using components from the library, import them directly from their respective directories:

```tsx
import { TextField, Button } from '@/components/common/form';
import { Card } from '@/components/common/data-display';
import { AppLayout } from '@/components/layout';

export default function MyPage() {
  return (
    <AppLayout>
      <Card title="My Form">
        <TextField label="Name" />
        <Button variant="primary">Submit</Button>
      </Card>
    </AppLayout>
  );
}
```

## Component Best Practices

1. **Use TypeScript Props Interfaces**: Define clear prop interfaces for all components
2. **Component Documentation**: Include JSDoc comments for all components
3. **Default Props**: Provide sensible default props where applicable
4. **Error Handling**: Include proper error states and fallbacks
5. **Accessibility**: Ensure components meet WCAG accessibility standards
6. **Responsive Design**: Components should work across different screen sizes
7. **Performance**: Use React.memo for expensive components when appropriate

## Creating New Components

When creating new components:

1. Place them in the appropriate directory based on their purpose
2. Create a clear and concise TypeScript interface for props
3. Include comprehensive JSDoc documentation
4. Add appropriate test cases
5. Consider reusability and composability 