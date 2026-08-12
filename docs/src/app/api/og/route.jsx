/**
 * Generates the social preview image for any docs page.
 *
 *   GET /api/og?p=docs/endpoints&v=1
 *
 * The URL is built by `getOpenGraphImage()` in lib/metadata.js, which every
 * page's `openGraph.images` points at. Title, description and section are
 * re-resolved here from the MDX source rather than passed in the query string,
 * so the card can never drift from the page and the URL stays short.
 *
 * Runs on the Node runtime, not edge: docs are served by a standalone Next
 * server on Cloud Run, which has no edge runtime. `next/og` needs its wasm
 * decoder traced into the standalone bundle — see outputFileTracingIncludes in
 * next.config.mjs.
 */

import fs from 'fs'
import path from 'path'

import { ImageResponse } from 'next/og'

import { resolveOgPage } from '../../../lib/og-page.js'
import { siteConfig } from '../../../lib/site-config.js'
import {
  OG_SIZE,
  OG_COLORS,
  TITLE_LIMIT,
  DESCRIPTION_LIMIT,
  titleFontSize,
  truncate,
} from '../../../lib/og-theme.js'

// Cards are pure functions of the page content, so they can sit in a CDN for a
// long time; `v` in the URL is what invalidates them when the design changes.
const CACHE_CONTROL = 'public, max-age=3600, s-maxage=31536000, stale-while-revalidate=86400'

/**
 * Assets live under public/, which is copied verbatim into the runtime image.
 * The candidates cover `next dev` (cwd = docs/src) and the standalone server
 * (cwd = /app).
 */
function assetPath(relative) {
  const candidates = [
    path.join(process.cwd(), 'public', relative),
    path.join(process.cwd(), 'src', 'public', relative),
  ]
  return candidates.find(candidate => fs.existsSync(candidate)) || null
}

function readAsset(relative) {
  const resolved = assetPath(relative)
  if (!resolved) throw new Error(`OG asset missing: ${relative}`)
  return fs.readFileSync(resolved)
}

/**
 * satori cannot read woff2 and renders a variable font at its default instance
 * only, so these are static-instance TTF subsets generated from the woff2 faces
 * the site itself uses. Loaded once per server process.
 */
let cachedAssets = null

function loadAssets() {
  if (!cachedAssets) {
    cachedAssets = {
      logo: `data:image/png;base64,${readAsset('logo/rhesis-mark-og.png').toString('base64')}`,
      fonts: [
        { name: 'Sora', data: readAsset('fonts/og/Sora-700.ttf'), weight: 700, style: 'normal' },
        { name: 'Geist', data: readAsset('fonts/og/Geist-400.ttf'), weight: 400, style: 'normal' },
        { name: 'Geist', data: readAsset('fonts/og/Geist-500.ttf'), weight: 500, style: 'normal' },
        {
          name: 'Geist Mono',
          data: readAsset('fonts/og/GeistMono-500.ttf'),
          weight: 500,
          style: 'normal',
        },
      ],
    }
  }
  return cachedAssets
}

function Card({ title, description, section, logo }) {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '64px 72px',
        backgroundColor: OG_COLORS.canvas,
        fontFamily: 'Geist',
      }}
    >
      {/* Brand wash, echoing the gradient backdrop on the site itself. */}
      <div
        style={{
          position: 'absolute',
          top: -240,
          left: -180,
          width: 900,
          height: 760,
          backgroundImage:
            'radial-gradient(circle at center, rgba(80,185,224,0.40) 0%, rgba(80,185,224,0.12) 45%, rgba(80,185,224,0) 70%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: -260,
          right: -160,
          width: 820,
          height: 700,
          backgroundImage:
            'radial-gradient(circle at center, rgba(253,216,3,0.28) 0%, rgba(253,216,3,0.08) 48%, rgba(253,216,3,0) 72%)',
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {/* satori renders a plain <img> — next/image has no place in an OG card */}
          <img src={logo} width={58} height={38} alt="" />
          <span
            style={{
              marginLeft: 16,
              fontFamily: 'Sora',
              fontWeight: 700,
              fontSize: 30,
              letterSpacing: '-0.01em',
              color: OG_COLORS.heading,
            }}
          >
            Rhesis AI
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            padding: '11px 24px',
            borderRadius: 999,
            border: `1px solid ${OG_COLORS.border}`,
            backgroundColor: 'rgba(255,255,255,0.72)',
            fontFamily: 'Geist Mono',
            fontWeight: 500,
            fontSize: 18,
            letterSpacing: '0.14em',
            color: OG_COLORS.textSecondary,
          }}
        >
          {section.toUpperCase()}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', marginTop: 24 }}>
        <div
          style={{
            fontFamily: 'Sora',
            fontWeight: 700,
            fontSize: titleFontSize(title),
            lineHeight: 1.12,
            letterSpacing: '-0.02em',
            color: OG_COLORS.heading,
          }}
        >
          {title}
        </div>
        {description ? (
          <div
            style={{
              marginTop: 26,
              fontSize: 28,
              lineHeight: 1.45,
              color: OG_COLORS.textSecondary,
            }}
          >
            {description}
          </div>
        ) : null}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: 26,
          borderTop: `1px solid ${OG_COLORS.border}`,
          fontFamily: 'Geist Mono',
          fontWeight: 500,
          fontSize: 20,
          color: OG_COLORS.textMuted,
        }}
      >
        <span>docs.rhesis.ai</span>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: 999,
              backgroundColor: OG_COLORS.blueCta,
            }}
          />
          <div
            style={{
              marginLeft: 8,
              width: 10,
              height: 10,
              borderRadius: 999,
              backgroundColor: OG_COLORS.yellow,
            }}
          />
        </div>
      </div>
    </div>
  )
}

export async function GET(request) {
  const urlPath = new URL(request.url).searchParams.get('p') || ''

  try {
    const { logo, fonts } = loadAssets()
    const page = resolveOgPage(urlPath)

    return new ImageResponse(
      (
        <Card
          title={truncate(page.title, TITLE_LIMIT)}
          description={truncate(page.description, DESCRIPTION_LIMIT)}
          section={page.section}
          logo={logo}
        />
      ),
      {
        ...OG_SIZE,
        fonts,
        headers: { 'Cache-Control': CACHE_CONTROL },
      }
    )
  } catch (error) {
    // A broken card must not mean a broken link preview: fall back to the
    // static site image rather than serving a 500 to a crawler.
    console.error('OG image generation failed for', urlPath, error)
    return Response.redirect(`${siteConfig.siteUrl}${siteConfig.defaultImage}`, 302)
  }
}
