'use client';

import LoginSection from '@/components/auth/LoginSection';
import AuthPageShell from '@/components/auth/AuthPageShell';

export default function RegisterPage() {
  return (
    <AuthPageShell>
      <LoginSection isRegistration />
    </AuthPageShell>
  );
}
