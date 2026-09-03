import { redirect } from 'next/navigation';

/** Deep-link entry: opens the create drawer on the endpoints list. */
export default async function NewEndpointPage() {
  redirect('/endpoints?create=1');
}
