'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import SwaggerEndpointForm from '@/app/(protected)/endpoints/components/SwaggerEndpointForm';
import { PageContainer } from '@toolpad/core/PageContainer';
import { CircularProgress, Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default function SwaggerEndpointPage() {
  const params = useParams<{ identifier: string }>();
  const { data: session } = useSession();
  const [projectName, setProjectName] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProjectName = async () => {
      if (!params?.identifier || !session?.session_token) {
        setLoading(false);
        return;
      }

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const projectsClient = apiFactory.getProjectsClient();
        const project = await projectsClient.getProject(params.identifier);
        setProjectName(project.name);
      } catch (error) {
        console.error('Error fetching project:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchProjectName();
  }, [params?.identifier, session]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  const breadcrumbs = [
    { title: 'Projects', path: '/projects' },
    {
      title: projectName || 'Project',
      path: `/projects/${params.identifier}`,
    },
    { title: 'Add Swagger Endpoint' },
  ];

  return (
    <PageContainer title="New Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageContainer>
  );
}
