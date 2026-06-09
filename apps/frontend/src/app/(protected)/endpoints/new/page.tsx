import { redirect } from 'next/navigation';

export default function NewEndpointPage() {
  redirect('/endpoints?create=1');
}
