import { Metadata } from 'next';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// Generate metadata for the page
export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const session = (await auth()) as { session_token: string } | null;

    // If no session (like during warmup), return basic metadata
    if (!session?.session_token) {
      return {
        title: `Task ${identifier}`,
        description: `Details for Task ${identifier}`,
      };
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const tasksClient = apiFactory.getTasksClient();
    const task = await tasksClient.getTask(identifier);

    return {
      title: task.title || `Task ${identifier}`,
      description: `Task details for: ${task.title || identifier}`,
    };
  } catch (_error) {
    return {
      title: 'Task Details',
    };
  }
}

export default function TaskDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
