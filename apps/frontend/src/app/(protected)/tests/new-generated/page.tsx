import { auth } from '@/auth';
import TestGenerationFlow from './components/TestGenerationFlow';

export default async function GenerateTestsPage() {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <div style={{ padding: 0 }}>
      <TestGenerationFlow sessionToken={session.session_token} />
    </div>
  );
}
