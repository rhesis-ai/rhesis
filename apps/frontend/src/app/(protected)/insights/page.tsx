import * as React from 'react';
import { auth } from '@/auth';
import InsightsPage from './components/InsightsPage';

export default async function InsightsRoutePage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return <InsightsPage sessionToken={session.session_token} />;
}
