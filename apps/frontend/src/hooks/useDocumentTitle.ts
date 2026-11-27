import { useEffect } from 'react';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';
import { DEFAULT_PRODUCT_NAME } from '@/config/branding';

/**
 * Titles of the mounted `useDocumentTitle` callers, most recent last. Only the
 * last one may re-apply its title: two callers on one page (a list and the
 * drawer over it) would otherwise keep overwriting each other's title from
 * their observers, freezing the tab.
 */
const titleStack: { token: symbol; title: string }[] = [];

function topTitle(): { token: symbol; title: string } | undefined {
  return titleStack[titleStack.length - 1];
}

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
    const entry = { token: Symbol(title), title: fullTitle };
    titleStack.push(entry);
    document.title = fullTitle;

    // Streamed route metadata can insert its <title> after this effect and
    // win; re-apply ours, but not once a navigation has moved off this page.
    const observer = new MutationObserver(() => {
      if (
        topTitle()?.token === entry.token &&
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
      const wasTop = topTitle()?.token === entry.token;
      titleStack.splice(titleStack.indexOf(entry), 1);
      // Hand the tab back to the title underneath (e.g. a list page under a
      // drawer), but leave a title the next page has already set alone.
      if (wasTop && document.title === fullTitle) {
        document.title = topTitle()?.title ?? (previousTitle || productName);
      }
    };
  }, [title, productName]);
}
