import { useEffect } from 'react';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { DEFAULT_PRODUCT_NAME } from '@/config/branding';

/**
 * Sets the document title for client components, which cannot use
 * `generateMetadata`.
 *
 * The suffix comes from the resolved branding rather than a literal, so a
 * rebranded organisation does not see "Tests | Rhesis AI" in its browser tab.
 * `NavigationItemsContext` is fed by the root layout, so it also follows a
 * branding change made in the settings page without a reload.
 */
export function useDocumentTitle(title: string | null) {
  const { branding } = useNavigationItems();
  const productName = branding?.productName ?? DEFAULT_PRODUCT_NAME;

  useEffect(() => {
    if (title) {
      // Mirrors the root layout's metadata template, '%s | <product name>'.
      document.title = `${title} | ${productName}`;
    }

    // Cleanup function to restore default title when component unmounts
    return () => {
      document.title = productName;
    };
  }, [title, productName]);
}
