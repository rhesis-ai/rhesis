import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';

// Generate metadata for the page
export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const session = await auth();

    // If no session (like during warmup), return basic metadata
    if (!session || session.error) {
      return {
        title: `Task ${identifier}`,
        description: `Details for Task ${identifier}`,
      };
    }

    const apiFactory = await createServerApiFactory();
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
