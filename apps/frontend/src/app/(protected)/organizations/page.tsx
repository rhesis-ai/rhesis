import { redirect } from 'next/navigation';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function OrganizationRedirectPage({ params }: PageProps) {
  // Redirect to dashboard
  redirect('/dashboard');
}
