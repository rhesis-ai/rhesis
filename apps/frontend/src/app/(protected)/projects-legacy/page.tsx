import * as React from 'react';
import Typography from '@mui/material/Typography';
import { Box } from '@mui/material';
import ProjectsTable from './components/ProjectsTable';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// Mock data for projects
const mockProjects = [
  {
    id: '1',
    name: 'Financial Assistant',
    description: 'AI-powered platform for financial data retrieval, research, and analysis',
    environment: 'development',
    useCase: 'advisor',
    tags: ['finance', 'advisory', 'regulatory'],
    createdAt: '2024-03-05',
    user: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'John Doe',
      email: 'john.doe@example.com',
      family_name: 'Doe',
      given_name: 'John',
      picture: 'https://example.com/avatar.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    owner: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'Harry Cruz',
      email: 'harry.cruz@example.com',
      family_name: 'Cruz',
      given_name: 'Harry',
      picture: 'https://example.com/avatar2.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    organization: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'ACME Corp',
      description: 'A leading technology company',
      email: 'info@acme.com',
      user_id: '12345678-1234-1234-1234-123456789012'
    },
  },
  {
    id: '2',
    name: 'Insurance Chatbot',
    description: 'Customer service chatbot for insurance claims',
    environment: 'production',
    useCase: 'chatbot',
    tags: ['insurance', 'customer-service', 'compliance'],
    createdAt: '2024-03-15',
    user: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'John Doe',
      email: 'john.doe@example.com',
      family_name: 'Doe',
      given_name: 'John',
      picture: 'https://example.com/avatar.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    owner: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'Harry Cruz',
      email: 'harry.cruz@example.com',
      family_name: 'Cruz',
      given_name: 'Harry',
      picture: 'https://example.com/avatar2.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    organization: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'ACME Corp',
      description: 'A leading technology company',
      email: 'info@acme.com',
      user_id: '12345678-1234-1234-1234-123456789012'
    },
  },
  {
    id: '3',
    name: 'Healthcare Assistant',
    description: 'Medical information assistant for patients',
    environment: 'staging',
    useCase: 'assistant',
    tags: ['healthcare', 'patient-care', 'HIPAA'],
    createdAt: '2024-03-10',
    user: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'John Doe',
      email: 'john.doe@example.com',
      family_name: 'Doe',
      given_name: 'John',
      picture: 'https://example.com/avatar.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    owner: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'Harry Cruz',
      email: 'harry.cruz@example.com',
      family_name: 'Cruz',
      given_name: 'Harry',
      picture: 'https://example.com/avatar2.png',
      organization_id: '12345678-1234-1234-1234-123456789012'
    },
    organization: {
      id: '12345678-1234-1234-1234-123456789012',
      name: 'ACME Corp',
      description: 'A leading technology company',
      email: 'info@acme.com',
      user_id: '12345678-1234-1234-1234-123456789012'
    },
  },
];

export default async function ProjectsPage() {
  try {
    const session = await auth();
    
    if (!session?.session_token) {
      throw new Error('No session token available');
    }
    
    // In the future, replace mockProjects with actual API call
    // const apiFactory = new ApiClientFactory(session.session_token);
    // const projectsClient = apiFactory.getProjectsClient();
    // const projects = await projectsClient.getProjects();
    
    return (
      <Box sx={{ p: 3 }}>
        <ProjectsTable projects={mockProjects} />
      </Box>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Error loading projects: {errorMessage}
        </Typography>
      </Box>
    );
  }
}
