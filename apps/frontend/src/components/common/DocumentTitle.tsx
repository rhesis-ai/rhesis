'use client';

import { useDocumentTitle } from '@/hooks/useDocumentTitle';

/** Lets a server component set the browser title through `useDocumentTitle`. */
export default function DocumentTitle({ title }: { title: string | null }) {
  useDocumentTitle(title);
  return null;
}
