import { notFound } from 'next/navigation';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import type { Project } from '@/utils/api-client/interfaces/project';
import ClientWrapper from './client-wrapper';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import {
  fetchProjectEnvironments,
  fetchProjectTraceMetrics,
  projectTraceMetricIds,
} from './components/project-data';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams?: Promise<Record<string, string | string[]>>;
}

export default async function ProjectDetailPage({ params }: PageProps) {
  await requireSession();

  const apiFactory = await createServerApiFactory();
  const projectsClient = apiFactory.getProjectsClient();
  const resolvedParams = await params;

  let project: Project;
  try {
    project = await projectsClient.getProject(resolvedParams.identifier);
  } catch (error) {
    // Projects deviate from the repo's 404-only notFoundIfEntityMissing pattern on
    // purpose. A deleted project comes back as 410 with a restore offer, but deleting
    // a project hard-drops every project_membership row and restoring does not
    // re-enroll anyone — so a restored project would be invisible to everyone. Treat
    // gone and missing the same way.
    if (isNotFoundApiError(error)) notFound();
    throw error;
  }

  // Members and Configuration tab data, so each tab opens with rows in place.
  const [members, environments, traceMetrics] = await Promise.all([
    prefetch(Capability.ProjectMember.READ, () =>
      apiFactory
        .forProject(project.id)
        .getProjectsClient()
        .getProjectMembers(project.id)
    ),
    prefetch(Capability.Experiment.READ, () =>
      fetchProjectEnvironments(apiFactory, project.id)
    ),
    prefetch(Capability.Metric.READ, () =>
      fetchProjectTraceMetrics(apiFactory, projectTraceMetricIds(project))
    ),
  ]);

  return (
    <ClientWrapper
      project={project}
      projectId={project.id}
      initialData={{ members, environments, traceMetrics }}
    />
  );
}
