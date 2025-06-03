# API Integration

This document explains how the Rhesis frontend application integrates with the Rhesis backend API.

## API Client Architecture

The Rhesis frontend communicates exclusively with the Rhesis backend API for all data operations and authentication. The frontend uses a centralized API client to handle all requests to the Rhesis backend. This client is built with:

- Type safety for request and response data
- Automatic authentication handling with Auth0 tokens
- Error handling and retries
- Request caching where appropriate
- Consistent error formatting

## Rhesis Backend API

The Rhesis backend API serves as the intermediary between the frontend and various services:

- **Authentication**: The backend handles Auth0 authentication and token management
- **Data Storage**: The backend manages all data persistence and retrieval
- **Business Logic**: Complex business logic is implemented in the backend
- **External Service Integration**: The backend integrates with any third-party services

All frontend requests are routed through the Rhesis backend API, which provides a unified interface for the frontend application.

## API Client Implementation

The API client is implemented in `src/utils/api-client/`:

```
src/utils/api-client/
├── index.ts              # Main export file
├── client.ts             # Base API client implementation
├── endpoints/            # API endpoint definitions
│   ├── auth.ts           # Authentication endpoints
│   ├── projects.ts       # Projects endpoints
│   ├── tests.ts          # Tests endpoints
│   └── ...               # Other endpoint groups
└── types/                # API type definitions
    ├── auth.ts           # Authentication types
    ├── projects.ts       # Projects types
    ├── tests.ts          # Tests types
    └── ...               # Other type groups
```

### Base Client

The base client is implemented in `src/utils/api-client/client.ts` and handles communication with the Rhesis backend API:

```tsx
import { getTokens } from '@/auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const tokens = getTokens();
  const headers = new Headers(options.headers);
  
  // Add authentication header if tokens exist
  if (tokens?.accessToken) {
    headers.append('Authorization', `Bearer ${tokens.accessToken}`);
  }
  
  // Add content type if not present
  if (!headers.has('Content-Type') && options.method !== 'GET') {
    headers.append('Content-Type', 'application/json');
  }
  
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });
  
  // Handle non-JSON responses
  const contentType = response.headers.get('Content-Type');
  if (contentType && !contentType.includes('application/json')) {
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText);
    }
    return response as unknown as T;
  }
  
  // Parse JSON response
  const data = await response.json();
  
  // Handle error responses
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data.message || response.statusText
    );
  }
  
  return data;
}
```

### Endpoint Definitions

API endpoints are defined in separate files for each resource, all targeting the Rhesis backend API:

```tsx
// src/utils/api-client/endpoints/projects.ts
import { apiClient } from '../client';
import type { Project, ProjectCreate, ProjectUpdate } from '../types/projects';

export const projectsApi = {
  getAll: async (params?: { skip?: number; limit?: number }) => {
    return apiClient<{ data: Project[]; total: number }>('/projects', {
      method: 'GET',
      ...(params && { 
        query: new URLSearchParams(params as Record<string, string>).toString() 
      }),
    });
  },
  
  getById: async (id: string) => {
    return apiClient<Project>(`/projects/${id}`, {
      method: 'GET',
    });
  },
  
  create: async (data: ProjectCreate) => {
    return apiClient<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  
  update: async (id: string, data: ProjectUpdate) => {
    return apiClient<Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },
  
  delete: async (id: string) => {
    return apiClient<void>(`/projects/${id}`, {
      method: 'DELETE',
    });
  },
};
```

### Type Definitions

API types are defined to match the Rhesis backend API response structures:

```tsx
// src/utils/api-client/types/projects.ts
export interface Project {
  id: string;
  name: string;
  description: string;
  createdAt: string;
  updatedAt: string;
  ownerId: string;
  status: 'active' | 'archived';
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: 'active' | 'archived';
}
```

## Using the API Client

### In Server Components

In server components, you can use the API client to communicate with the Rhesis backend:

```tsx
// app/(protected)/projects/page.tsx
import { projectsApi } from '@/utils/api-client/endpoints/projects';

export default async function ProjectsPage() {
  // Fetch data from the Rhesis backend API
  const { data: projects, total } = await projectsApi.getAll({ limit: 10 });
  
  return (
    <div>
      <h1>Projects ({total})</h1>
      <ul>
        {projects.map((project) => (
          <li key={project.id}>{project.name}</li>
        ))}
      </ul>
    </div>
  );
}
```

### In Client Components

In client components, you can use the API client with React hooks to communicate with the Rhesis backend:

```tsx
// components/projects/ProjectForm.tsx
'use client';

import { useState } from 'react';
import { projectsApi } from '@/utils/api-client/endpoints/projects';
import type { ProjectCreate } from '@/utils/api-client/types/projects';

export default function ProjectForm() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const data: ProjectCreate = {
        name,
        description: description || undefined,
      };
      
      // Send data to the Rhesis backend API
      await projectsApi.create(data);
      // Handle success (e.g., redirect, show message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      {error && <div className="error">{error}</div>}
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Project'}
      </button>
    </form>
  );
}
```

## Server Actions

For form submissions and mutations, you can use server actions that communicate with the Rhesis backend API:

```tsx
// app/(protected)/projects/actions.ts
'use server';

import { revalidatePath } from 'next/cache';
import { projectsApi } from '@/utils/api-client/endpoints/projects';
import type { ProjectCreate, ProjectUpdate } from '@/utils/api-client/types/projects';

export async function createProject(data: ProjectCreate) {
  try {
    // Create project through the Rhesis backend API
    await projectsApi.create(data);
    revalidatePath('/projects');
    return { success: true };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to create project' 
    };
  }
}

export async function updateProject(id: string, data: ProjectUpdate) {
  try {
    // Update project through the Rhesis backend API
    await projectsApi.update(id, data);
    revalidatePath(`/projects/${id}`);
    revalidatePath('/projects');
    return { success: true };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to update project' 
    };
  }
}

export async function deleteProject(id: string) {
  try {
    // Delete project through the Rhesis backend API
    await projectsApi.delete(id);
    revalidatePath('/projects');
    return { success: true };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to delete project' 
    };
  }
}
```

## API Configuration

The Rhesis backend API URL is configured in environment variables:

```
# .env.local
NEXT_PUBLIC_API_BASE_URL=https://api.rhesis.ai
```

For local development, you might point to a local instance of the Rhesis backend:

```
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001
```

## Error Handling

The API client includes centralized error handling for Rhesis backend API errors:

```tsx
// components/common/ErrorBoundary.tsx
'use client';

import { useEffect } from 'react';
import { ApiError } from '@/utils/api-client/client';

export default function ErrorBoundary({ 
  error, 
  reset 
}: { 
  error: Error; 
  reset: () => void;
}) {
  useEffect(() => {
    // Log error to monitoring service
    console.error(error);
  }, [error]);
  
  if (error instanceof ApiError) {
    // Handle API-specific errors from the Rhesis backend
    if (error.status === 401) {
      return (
        <div>
          <h2>Session expired</h2>
          <p>Please log in again.</p>
          <button onClick={() => window.location.href = '/login'}>
            Log In
          </button>
        </div>
      );
    }
    
    if (error.status === 403) {
      return (
        <div>
          <h2>Access denied</h2>
          <p>You don't have permission to access this resource.</p>
          <button onClick={() => window.location.href = '/dashboard'}>
            Go to Dashboard
          </button>
        </div>
      );
    }
  }
  
  // Generic error handling
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

## API Documentation

For detailed Rhesis backend API endpoint documentation, refer to the [API Endpoints](./api-endpoints.md) document. 