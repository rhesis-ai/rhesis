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
    if (!title) return;

    // Mirrors the root layout's metadata template, '%s | <product name>'.
    const fullTitle = `${title} | ${productName}`;
    const pathname = window.location.pathname;
    const previousTitle = document.title;
    document.title = fullTitle;

    // Streamed route metadata can insert its <title> after this effect and
    // win; re-apply ours, but not once a navigation has moved off this page.
    const observer = new MutationObserver(() => {
      if (
        window.location.pathname === pathname &&
        document.title !== fullTitle
      ) {
        document.title = fullTitle;
      }
    });
    // Next may add a new <title> or rewrite the existing one's text.
    observer.observe(document.head, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => {
      observer.disconnect();
      // Restore what was there (e.g. a list page under a drawer), but leave a
      // title the next page has already set alone.
      if (document.title === fullTitle) {
        document.title = previousTitle || productName;
      }
    };
  }, [title, productName]);
}
