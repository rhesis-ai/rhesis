import { useEffect } from 'react';

/**
 * Custom hook to dynamically set the document title
 * This is needed for client components that can't use generateMetadata
 */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    if (title) {
      // Use the same template pattern as the root layout: '%s | Rhesis AI'
      document.title = `${title} | Rhesis AI`;
    }

    // Cleanup function to restore default title when component unmounts
    return () => {
      document.title = 'Rhesis AI';
    };
  }, [title]);
}
