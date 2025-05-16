# State Management

This document explains the state management approach used in the Rhesis frontend application.

## State Management Architecture

The Rhesis frontend uses a hybrid state management approach:

1. **Server Components**: Data fetching and state management on the server
2. **React Context**: For global UI state and shared state across components
3. **Local Component State**: For component-specific state
4. **Server Actions**: For mutations and form submissions
5. **URL State**: For preserving state in the URL (e.g., filters, pagination)

This approach minimizes client-side state management while leveraging Next.js App Router features.

## Server Components

Server components handle data fetching and initial state:

```tsx
// app/(protected)/projects/page.tsx
import { projectsApi } from '@/utils/api-client/endpoints/projects';
import ProjectList from '@/components/projects/ProjectList';

export default async function ProjectsPage({
  searchParams,
}: {
  searchParams: { page?: string; limit?: string; search?: string };
}) {
  // Parse query parameters
  const page = parseInt(searchParams.page || '1', 10);
  const limit = parseInt(searchParams.limit || '10', 10);
  const search = searchParams.search || '';
  
  // Fetch data on the server
  const { data: projects, total } = await projectsApi.getAll({
    skip: (page - 1) * limit,
    limit,
    search,
  });
  
  return (
    <div>
      <h1>Projects ({total})</h1>
      <ProjectList 
        projects={projects} 
        total={total}
        page={page}
        limit={limit}
        search={search}
      />
    </div>
  );
}
```

## React Context

For global state, the application uses React Context:

### Context Definition

```tsx
// src/components/providers/ThemeProvider.tsx
'use client';

import { createContext, useContext, useState, useEffect } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>('system');
  
  // Initialize theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as Theme | null;
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);
  
  // Update localStorage when theme changes
  useEffect(() => {
    localStorage.setItem('theme', theme);
    
    // Apply theme to document
    const isDark = 
      theme === 'dark' || 
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    
    document.documentElement.classList.toggle('dark', isDark);
  }, [theme]);
  
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
```

### Context Usage

```tsx
// src/components/layout/ThemeToggle.tsx
'use client';

import { useTheme } from '@/components/providers/ThemeProvider';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  
  const toggleTheme = () => {
    if (theme === 'light') {
      setTheme('dark');
    } else if (theme === 'dark') {
      setTheme('system');
    } else {
      setTheme('light');
    }
  };
  
  return (
    <button onClick={toggleTheme}>
      {theme === 'light' && 'Light Mode'}
      {theme === 'dark' && 'Dark Mode'}
      {theme === 'system' && 'System Theme'}
    </button>
  );
}
```

### Context Setup

```tsx
// app/layout.tsx
import { ThemeProvider } from '@/components/providers/ThemeProvider';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

## Local Component State

For component-specific state, use React's built-in hooks:

```tsx
// src/components/projects/ProjectFilter.tsx
'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

export default function ProjectFilter({
  initialSearch = '',
}: {
  initialSearch?: string;
}) {
  const [search, setSearch] = useState(initialSearch);
  const router = useRouter();
  const pathname = usePathname();
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Update URL with search parameter
    const params = new URLSearchParams();
    if (search) {
      params.set('search', search);
    }
    
    router.push(`${pathname}?${params.toString()}`);
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search projects..."
      />
      <button type="submit">Search</button>
    </form>
  );
}
```

## Server Actions

For mutations and form submissions, use server actions:

```tsx
// app/(protected)/projects/actions.ts
'use server';

import { revalidatePath } from 'next/cache';
import { projectsApi } from '@/utils/api-client/endpoints/projects';
import type { ProjectCreate } from '@/utils/api-client/types/projects';

export async function createProject(formData: FormData) {
  const name = formData.get('name') as string;
  const description = formData.get('description') as string;
  
  if (!name) {
    return { success: false, error: 'Name is required' };
  }
  
  try {
    await projectsApi.create({
      name,
      description: description || undefined,
    });
    
    revalidatePath('/projects');
    return { success: true };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to create project' 
    };
  }
}
```

Using server actions in a form:

```tsx
// src/components/projects/ProjectForm.tsx
'use client';

import { useFormState } from 'react-dom';
import { createProject } from '@/app/(protected)/projects/actions';

const initialState = { success: false, error: null };

export default function ProjectForm() {
  const [state, formAction] = useFormState(createProject, initialState);
  
  return (
    <form action={formAction}>
      <div>
        <label htmlFor="name">Name</label>
        <input id="name" name="name" required />
      </div>
      
      <div>
        <label htmlFor="description">Description</label>
        <textarea id="description" name="description" />
      </div>
      
      {state.error && <div className="error">{state.error}</div>}
      
      <button type="submit">Create Project</button>
    </form>
  );
}
```

## URL State

For preserving state in the URL:

```tsx
// src/components/common/Pagination.tsx
'use client';

import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

interface PaginationProps {
  total: number;
  page: number;
  limit: number;
}

export default function Pagination({ total, page, limit }: PaginationProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  
  const totalPages = Math.ceil(total / limit);
  
  const createPageURL = (pageNumber: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', pageNumber.toString());
    return `${pathname}?${params.toString()}`;
  };
  
  return (
    <div className="pagination">
      {page > 1 && (
        <Link href={createPageURL(page - 1)}>Previous</Link>
      )}
      
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNumber) => (
        <Link
          key={pageNumber}
          href={createPageURL(pageNumber)}
          className={pageNumber === page ? 'active' : ''}
        >
          {pageNumber}
        </Link>
      ))}
      
      {page < totalPages && (
        <Link href={createPageURL(page + 1)}>Next</Link>
      )}
    </div>
  );
}
```

## State Management Best Practices

1. **Minimize Client-Side State**: Use server components for data fetching where possible
2. **Colocate State**: Keep state as close as possible to where it's used
3. **Use URL for Shareable State**: Store filters, pagination, and other shareable state in the URL
4. **Prefer Server Actions**: Use server actions for mutations instead of client-side API calls
5. **Context for Global State**: Use React Context for truly global state like theme, user preferences
6. **Avoid Prop Drilling**: Use context or composition to avoid excessive prop drilling
7. **Revalidate After Mutations**: Use `revalidatePath` to refresh data after mutations

## Example: Complex State Management

For complex state management needs, combine these approaches:

```tsx
// app/(protected)/projects/[id]/page.tsx
import { projectsApi } from '@/utils/api-client/endpoints/projects';
import ProjectDetails from '@/components/projects/ProjectDetails';
import { notFound } from 'next/navigation';

export default async function ProjectPage({
  params,
}: {
  params: { id: string };
}) {
  try {
    // Fetch data on the server
    const project = await projectsApi.getById(params.id);
    
    return <ProjectDetails project={project} />;
  } catch (error) {
    // Handle 404 errors
    notFound();
  }
}
```

```tsx
// src/components/projects/ProjectDetails.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { updateProject, deleteProject } from '@/app/(protected)/projects/actions';
import type { Project } from '@/utils/api-client/types/projects';

export default function ProjectDetails({ project }: { project: Project }) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const router = useRouter();
  
  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    const result = await updateProject(project.id, {
      name,
      description,
    });
    
    if (result.success) {
      setIsEditing(false);
    } else {
      setError(result.error);
    }
  };
  
  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this project?')) {
      return;
    }
    
    setIsDeleting(true);
    const result = await deleteProject(project.id);
    
    if (result.success) {
      router.push('/projects');
    } else {
      setError(result.error);
      setIsDeleting(false);
    }
  };
  
  if (isEditing) {
    return (
      <form onSubmit={handleUpdate}>
        {/* Edit form fields */}
        {error && <div className="error">{error}</div>}
        <div className="actions">
          <button type="submit">Save</button>
          <button type="button" onClick={() => setIsEditing(false)}>
            Cancel
          </button>
        </div>
      </form>
    );
  }
  
  return (
    <div>
      <h1>{project.name}</h1>
      <p>{project.description}</p>
      <div className="actions">
        <button onClick={() => setIsEditing(true)}>Edit</button>
        <button 
          onClick={handleDelete} 
          disabled={isDeleting}
        >
          {isDeleting ? 'Deleting...' : 'Delete'}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
} 