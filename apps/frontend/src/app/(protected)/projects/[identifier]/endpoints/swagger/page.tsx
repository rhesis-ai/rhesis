'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import SwaggerEndpointForm from '@/app/(protected)/endpoints/components/SwaggerEndpointForm';
import { PageLayout } from '@/components/layout/PageLayout';
import { CircularProgress, Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

export default function SwaggerEndpointPage() {
  const params = useParams<{ identifier: string }>();
  const { data: session, status } = useSession();
  const [projectName, setProjectName] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProjectName = async () => {
      if (!params?.identifier || !isAuthenticated(status)) {
        setLoading(false);
        return;
      }

      try {
        const apiFactory = new ApiClientFactory();
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
  }, [params?.identifier, session, status]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  const breadcrumbs = [
    { label: 'Projects', href: '/projects' },
    { label: projectName || 'Project', href: `/projects/${params.identifier}` },
    { label: 'Add Swagger Endpoint' },
  ];

  return (
    <PageLayout title="New Swagger Endpoint" breadcrumbs={breadcrumbs}>
      <SwaggerEndpointForm />
    </PageLayout>
  );
}
