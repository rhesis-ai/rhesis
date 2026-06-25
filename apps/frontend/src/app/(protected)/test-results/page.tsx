import { redirect } from 'next/navigation';
import { INSIGHTS_PATH } from '@/constants/paths';

export default function TestResultsRedirectPage() {
  redirect(INSIGHTS_PATH);
}
