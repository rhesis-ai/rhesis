import { redirect } from 'next/navigation';
import { INSIGHTS_PATH } from '@/constants/paths';

export default function DashboardRedirectPage() {
  redirect(INSIGHTS_PATH);
}
