import { redirect } from 'next/navigation';

export default async function GenerationRedirectPage() {
  redirect('/tests?openGeneration=true');
}
