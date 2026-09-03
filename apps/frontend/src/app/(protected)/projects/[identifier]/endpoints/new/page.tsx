import { redirect } from 'next/navigation';

interface NewProjectEndpointPageProps {
  params: Promise<{ identifier: string }>;
}

/** Deep-link entry: opens the create drawer with project pre-selected. */
export default async function NewProjectEndpointPage({
  params,
}: NewProjectEndpointPageProps) {
  const { identifier } = await params;
  redirect(`/endpoints?create=1&projectId=${encodeURIComponent(identifier)}`);
}
