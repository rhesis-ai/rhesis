import { test, expect } from '@playwright/test';

/**
 * Guards the laptop zoom ladder defined in `src/styles/viewport-scaling.css`.
 *
 * Three things can silently regress here and each has bitten before:
 *  1. the ladder itself drifting out of step with the breakpoints,
 *  2. an uncompensated `vh` inside the zoomed subtree leaving a dead strip,
 *  3. a body-portalled overlay being pulled *into* the zoomed subtree, which
 *     double-applies the zoom to MUI's JS-computed position.
 */

/** [viewport width, expected computed zoom on the scale root] */
const LADDER: [number, string][] = [
  [390, '1'],
  [768, '1'],
  [1023, '1'],
  [1024, '1'],
  [1280, '1'],
  [1399, '1'],
  [1400, '0.85'],
  [1512, '0.85'],
  [1600, '0.85'],
  [1700, '0.9'],
  [1728, '0.9'],
  [1800, '0.9'],
  [1920, '1'],
  [2560, '1'],
];

test('zoom ladder matches the breakpoints and adds no overflow', async ({
  page,
}) => {
  test.setTimeout(180_000);

  for (const [width, expectedZoom] of LADDER) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/architect', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(700);

    const m = await page.evaluate(() => {
      const root = document.querySelector('[data-ui-scale-root]');
      const de = document.documentElement;
      return {
        found: !!root,
        zoom: root ? getComputedStyle(root).zoom : null,
        uiScale: getComputedStyle(de).getPropertyValue('--ui-scale').trim(),
        overflowX: de.scrollWidth - de.clientWidth,
      };
    });

    expect(m.found, `scale root missing at ${width}px`).toBe(true);
    expect(`${parseFloat(String(m.zoom))} @${width}`).toBe(
      `${parseFloat(expectedZoom)} @${width}`
    );
    // --ui-scale must track the zoom, or every scaledVh() is wrong.
    // (Compared numerically — the CSS minifier rewrites `0.85` to `.85`.)
    expect(`${parseFloat(m.uiScale)} @${width}`).toBe(
      `${parseFloat(expectedZoom)} @${width}`
    );
    expect(
      m.overflowX,
      `horizontal overflow at ${width}px`
    ).toBeLessThanOrEqual(0);
  }
});

test('full-height shell tracks the real viewport under zoom', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await page.goto('/architect', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  const m = await page.evaluate(() => {
    const nav = document.querySelector('nav');
    return {
      navHeight: nav ? Math.round(nav.getBoundingClientRect().height) : null,
      innerHeight: window.innerHeight,
    };
  });

  // Uncompensated this was 786 against a 982px window — a visible dead strip.
  expect(m.navHeight).not.toBeNull();
  expect(Math.abs((m.navHeight as number) - m.innerHeight)).toBeLessThanOrEqual(
    2
  );
});

test('portalled overlays stay outside the zoomed subtree', async ({ page }) => {
  await page.setViewportSize({ width: 1512, height: 982 });
  await page.goto('/architect', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // The Next.js dev-overlay portal sits above the sidebar and swallows clicks.
  await page.addStyleTag({
    content: 'nextjs-portal { display: none !important }',
  });

  const account = page
    .locator('button, [role="button"]')
    .filter({ hasText: /Local Admin/i })
    .first();
  await expect(account).toBeVisible();
  const anchor = await account.boundingBox();
  expect(anchor).not.toBeNull();

  await account.click();
  await page.waitForTimeout(700);

  const m = await page.evaluate(() => {
    const paper = document.querySelector('.MuiPopover-paper, .MuiMenu-paper');
    if (!paper) return null;
    const b = paper.getBoundingClientRect();
    const root = document.querySelector('[data-ui-scale-root]');
    return {
      insideScaleRoot: !!root && root.contains(paper),
      zoomOnPaper: getComputedStyle(paper).zoom,
      paintedTop: Math.round(b.top),
      paintedBottom: Math.round(b.top + b.height),
      inlineTop: (paper as HTMLElement).style.top,
    };
  });

  expect(m).not.toBeNull();
  const r = m as NonNullable<typeof m>;

  // The whole point of scoping zoom to the app subtree.
  expect(r.insideScaleRoot).toBe(false);
  expect(r.zoomOnPaper).toBe('1');

  // MUI positions this popover by writing a px `top`. If the paper were inside
  // the zoomed subtree that value would be multiplied by the zoom on paint.
  const inline = parseFloat(r.inlineTop);
  expect(Number.isNaN(inline)).toBe(false);
  expect(Math.abs(r.paintedTop - inline)).toBeLessThanOrEqual(2);

  // ...and it should actually sit against the button that opened it.
  const anchorTop = (anchor as NonNullable<typeof anchor>).y;
  expect(Math.abs(r.paintedBottom - anchorTop)).toBeLessThanOrEqual(12);
});
