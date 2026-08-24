import * as React from 'react';
import { Metadata } from 'next';
import { cookies } from 'next/headers';
import ThemeAwareLogo from '../components/common/ThemeAwareLogo';
import '../styles/fonts.css';
import '../styles/viewport-scaling.css';
import '../styles/nav-density.css';
// Side-effect import: registers EE features into core's extension
// registries at module load. The actual @rhesis/ee-frontend import is
// contained in ee_bootstrap.ts (the only file allowed to do so). This
// pulls EE registrations into the server bundle; the same module is also
// pulled into the client bundle via consumers like the organization
// settings page, so registry state is populated wherever it is read.
import '../ee_bootstrap';
import '../lib/org-settings-tabs-bootstrap';
import {
  ScienceIcon,
  BiotechIcon,
  VpnKeyIcon,
  TestRunsIcon,
  AssessmentIcon,
  CategoryIcon,
  AutoGraphIcon,
  SmartToyIcon,
  EndpointsIcon,
  TasksIcon,
  KnowledgeIcon,
  RequirementsIcon,
  KidStarIcon,
  ForumIcon,
  RateReviewIcon,
  TracesIcon,
  PlaygroundIcon,
  AccountTreeIcon,
  EngineeringIcon,
  BuildIcon,
} from '@/components/icons';
import { auth } from '../auth';
import { handleSignIn, handleSignOut } from '../actions/auth';
import { LayoutContent } from '../components/layout/LayoutContent';
import { createServerApiFactory } from '../utils/api-client/server-factory';
import { getServerActiveProjectId } from '../utils/server-active-project';
import { fetchQuickStartEnabledServer } from '../utils/quick_start.server';
import {
  type NavigationItem,
  type BrandingProps,
  type AuthenticationProps,
} from '../types/navigation';
import { type Project } from '../utils/api-client/interfaces/project';
import { type Organization } from '../utils/api-client/interfaces/organization';
import { type UserSettings } from '../utils/api-client/interfaces/user';
import { type Session } from 'next-auth';
import ThemeContextProvider from '../components/providers/ThemeProvider';
import { getServerBranding, type BrandFont } from '../config/branding';
import { BACKGROUND_DEFAULT } from '../styles/theme-background';
import { Capability } from '../constants/capabilities';

// Mark this layout as dynamic since it uses server-side authentication
export const dynamic = 'force-dynamic';

/**
 * Sets `data-theme-mode` before first paint when the visitor has no stored
 * preference, so the browser's `prefers-color-scheme` decides. Kept inline and
 * render-blocking on purpose — deferring it would paint light first and flash.
 */
const THEME_MODE_SCRIPT = `(function(){try{
  var el=document.documentElement;
  if(el.getAttribute('data-theme-mode'))return;
  var stored=localStorage.getItem('theme-mode');
  var mode=(stored==='dark'||stored==='light')?stored:
    (window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
  el.setAttribute('data-theme-mode',mode);
}catch(e){}})();`;

/**
 * Paints the page background from `data-theme-mode` before React hydrates.
 *
 * The script above fixes which mode the provider picks, but not the first
 * paint: MUI's styles are server-rendered through `AppRouterCacheProvider`
 * from `initialMode`, so without a cookie the served HTML is always light. A
 * dark-OS visitor would see a white page until hydration swapped it — measured
 * at over a second on a throttled CPU. These two rules are the only styling
 * that has to be right before hydration; everything else is below the fold of
 * perception.
 *
 * The values come from `theme-background.ts`, not `theme.ts` — that file is
 * `'use client'`, and importing a value from it here (a Server Component)
 * yields a client reference, which rendered `background-color:undefined`.
 */
const THEME_MODE_STYLE = (['dark', 'light'] as const)
  .map(
    mode => `html[data-theme-mode='${mode}']{color-scheme:${mode}}
html[data-theme-mode='${mode}'],html[data-theme-mode='${mode}'] body{background-color:${BACKGROUND_DEFAULT[mode]}}`
  )
  .join('\n');

function buildFontFaceCss(font: BrandFont): string {
  const weights = ['300', '400', '700'];
  return weights
    .map(
      w =>
        `@font-face{font-family:"${font.family}";font-weight:${w};font-style:normal;font-display:swap;src:url("/brand-fonts/${font.slug}-${w}.ttf") format("truetype")}`
    )
    .join('\n');
}

// This function will be used to get navigation items with dynamic data
async function getNavigationItems(
  session: Session | null,
  // Only a fallback: the real organisation name replaces it below whenever the
  // lookup succeeds. It matters on the paths where it can't — no session yet, or
  // the request failed — since that is where a branded deployment would
  // otherwise flash "Rhesis AI" in its sidebar.
  fallbackName: string
): Promise<{
  items: NavigationItem[];
  organizationName: string;
  organization: Organization | null;
}> {
  'use server';

  let organizationName = fallbackName;
  let organization: Organization | null = null;

  if (session?.user?.organization_id && !session.error) {
    try {
      const clientFactory = await createServerApiFactory();
      organization = await clientFactory
        .getOrganizationsClient()
        .getOrganization(session.user.organization_id);
      if (organization?.name) {
        organizationName = organization.name;
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes('Unauthorized')) {
      }
    }
  }

  const navItems = [
    {
      kind: 'page',
      segment: 'architect',
      title: 'Architect',
      icon: <EngineeringIcon key="architect-icon" />,
      requiredPermission: Capability.Architect.READ,
    },
    // DEFINE section — core definition items
    {
      kind: 'header',
      title: 'Define',
    },
    {
      kind: 'page',
      segment: 'knowledge',
      title: 'Knowledge',
      icon: <KnowledgeIcon key="knowledge-icon" />,
      requiredPermission: Capability.Source.READ,
    },
    {
      kind: 'page',
      segment: 'requirements',
      title: 'Requirements',
      icon: <RequirementsIcon key="requirements-icon" />,
      requiredPermission: Capability.Requirement.READ,
    },
    {
      kind: 'page',
      segment: 'metrics',
      title: 'Metrics',
      icon: <AutoGraphIcon key="metrics-icon" />,
      requiredPermission: Capability.Metric.READ,
    },
    // GENERATE section — creation and exploration tools
    {
      kind: 'header',
      title: 'Generate',
    },
    {
      kind: 'page',
      segment: 'playground',
      title: 'Playground',
      icon: <PlaygroundIcon key="playground-icon" />,
      requiredPermission: Capability.Playground.USE,
    },
    {
      kind: 'page',
      segment: 'explorer',
      title: 'Explorer',
      icon: <AccountTreeIcon key="explorer-icon" />,
      requiredPermission: Capability.Explorer.READ,
    },
    {
      kind: 'page',
      segment: 'tests',
      title: 'Tests',
      icon: <ScienceIcon key="tests-icon" />,
      requiredPermission: Capability.Test.READ,
    },
    {
      kind: 'page',
      segment: 'test-sets',
      title: 'Test Sets',
      icon: <CategoryIcon key="test-sets-icon" />,
      requiredPermission: Capability.TestSet.READ,
    },
    // IMPROVE section — analysis and iteration
    {
      kind: 'header',
      title: 'Improve',
    },
    {
      kind: 'page',
      segment: 'insights',
      title: 'Insights',
      icon: <AssessmentIcon key="insights-icon" />,
      requiredPermission: Capability.TestResult.READ,
    },
    {
      kind: 'page',
      segment: 'test-runs',
      title: 'Test Runs',
      icon: <TestRunsIcon key="test-runs-icon" />,
      requiredPermission: Capability.TestRun.READ,
    },
    {
      kind: 'page',
      segment: 'experiments',
      title: 'Experiments',
      icon: <BiotechIcon key="experiments-icon" />,
      requiredPermission: Capability.Experiment.READ,
    },
    {
      kind: 'page',
      segment: 'traces',
      title: 'Traces',
      icon: <TracesIcon key="traces-icon" />,
      requiredPermission: Capability.Telemetry.READ,
    },
    {
      kind: 'page',
      segment: 'annotations',
      title: 'Annotations',
      icon: <RateReviewIcon key="annotations-icon" />,
      requiredAnyOf: [Capability.TestResult.READ, Capability.Telemetry.READ],
    },
    {
      kind: 'page',
      segment: 'tasks',
      title: 'Tasks',
      icon: <TasksIcon key="tasks-icon" />,
      requiredPermission: Capability.Task.READ,
    },
    // CONNECT section — tools and infrastructure (collapsible, collapsed by default)
    {
      kind: 'header',
      title: 'CONNECT',
      collapsible: true,
      defaultCollapsed: true,
    },
    {
      kind: 'page',
      segment: 'endpoints',
      title: 'Endpoints',
      icon: <EndpointsIcon key="endpoints-icon" />,
      requiredPermission: Capability.Endpoint.READ,
    },
    {
      kind: 'page',
      segment: 'models',
      title: 'Models',
      icon: <SmartToyIcon key="models-icon" />,
      requiredPermission: Capability.Model.READ,
    },
    {
      kind: 'page',
      segment: 'tools',
      title: 'Tools',
      icon: <BuildIcon key="tool-icon" />,
      requiredPermission: Capability.Tool.READ,
    },
    {
      kind: 'page',
      segment: 'tokens',
      title: 'API',
      icon: <VpnKeyIcon key="tokens-icon" />,
      requiredPermission: Capability.Token.MANAGE,
    },
    // Divider before footer links
    {
      kind: 'divider',
    },
    // Footer external links (rendered as a white card in the sidebar)
    {
      kind: 'link',
      title: 'Star Rhesis',
      href: 'https://github.com/rhesis-ai/rhesis',
      icon: <KidStarIcon key="star-icon" />,
      external: true,
    },
    {
      kind: 'action',
      title: 'Support',
      action: 'support',
      icon: <ForumIcon key="support-icon" />,
    },
  ];

  return {
    items: navItems as NavigationItem[],
    organizationName,
    organization,
  };
}

/**
 * A function rather than a static `metadata` object so the favicon and product
 * name are resolved per request from the environment, letting one image serve
 * deployments with different branding.
 */
export async function generateMetadata(): Promise<Metadata> {
  const { faviconUrl, productName, isDefaultProductName } = getServerBranding();

  return {
    title: {
      // Pages set a bare `title` ('Architect'); this supplies the suffix.
      template: `%s | ${productName}`,
      default: productName,
    },
    // The Rhesis tagline would be wrong copy on a rebranded deployment, so a
    // configured product name replaces it rather than being appended to it.
    description: isDefaultProductName
      ? 'Rhesis AI | OSS Gen AI Testing Platform'
      : productName,
    icons: {
      icon: faviconUrl,
    },
  };
}

const AUTHENTICATION: AuthenticationProps = {
  signIn: handleSignIn,
  signOut: handleSignOut,
};

export default async function RootLayout(props: { children: React.ReactNode }) {
  const session = await auth().catch(() => null);
  // Only an explicit choice pins the mode. When the cookie is absent we leave
  // `data-theme-mode` off the <html> element so the pre-paint script below can
  // resolve it from the browser's `prefers-color-scheme` — stamping 'light'
  // here made `ThemeContextProvider`'s layout effect match the attribute and
  // return early, so a first-time visitor never got their system dark mode.
  const themeCookie = (await cookies()).get('theme-mode')?.value;
  const storedThemeMode =
    themeCookie === 'dark' || themeCookie === 'light' ? themeCookie : undefined;

  // Branding is read here rather than in a client component because its env
  // vars carry no `NEXT_PUBLIC_` prefix — see `config/branding.ts`. Reading it
  // on the server and passing it down as props also keeps the server-rendered
  // markup and the hydrated tree in agreement.
  const deploymentBranding = getServerBranding();

  // Get navigation with dynamic organization name
  const {
    items: navigation,
    organizationName,
    organization,
  } = await getNavigationItems(session, deploymentBranding.productName);

  const branding: BrandingProps = {
    title: organizationName,
    logo: <ThemeAwareLogo productName={deploymentBranding.productName} />,
    iconUrl: deploymentBranding.faviconUrl,
    productName: deploymentBranding.productName,
    homeUrl: '/architect',
  };
  // Empty when `API_BASE_URL` is unset or blank — whichever of Helm,
  // docker-compose or the dev scripts supplies the environment — so
  // `getClientApiBaseUrl()` throws instead of silently using localhost;
  // a deployed frontend would otherwise point `/auth/*` at the visitor's
  // own machine.
  const runtimeEnvScript = `window.__ENV__=${JSON.stringify({
    apiBaseUrl: process.env.API_BASE_URL || '',
    brandPrimaryColor: deploymentBranding.primaryColor,
    brandFaviconUrl: deploymentBranding.faviconUrl,
    brandProductName: deploymentBranding.productName,
  }).replace(/</g, '\\u003c')};`;

  // Fetch the active project, and the full member-project list for the
  // switcher, server-side so the sidebar/switcher render on first paint
  // without a flash. Without `initialProjects`, `ActiveProjectProvider`
  // always issued a client-side `GET /projects/mine` on mount even though
  // the active project itself was already known here — this seeds that list
  // too so the client effect can skip the network round trip entirely on
  // the common case (falling back to fetching itself if this failed).
  let initialActiveProject: Project | null = null;
  let initialProjects: Project[] | null = null;
  // Seeds `useUserSettings`'s cache too (see `ActiveProjectProvider`), so
  // the `default_project` fallback lookup it otherwise does with a client
  // `GET /users/settings` — needed whenever there's no active-project cookie
  // yet, e.g. a brand-new session — is already answered.
  let initialUserSettings: UserSettings | null = null;
  const projectId = await getServerActiveProjectId();
  if (session && !session.error && session.user?.organization_id) {
    const factory = await createServerApiFactory();
    const [projectsResult, settingsResult] = await Promise.allSettled([
      factory.getProjectsClient().getMyProjects(),
      factory.getUsersClient().getUserSettings(),
    ]);

    if (projectsResult.status === 'fulfilled') {
      initialProjects = projectsResult.value;
      if (projectId) {
        initialActiveProject =
          projectsResult.value.find(p => String(p.id) === projectId) ?? null;
      }
    }
    if (settingsResult.status === 'fulfilled') {
      initialUserSettings = settingsResult.value;
    }
  }

  // Fetched once here (unauthenticated `GET /auth/providers`) and threaded
  // down via `QuickStartProvider` — see `fetchQuickStartEnabledServer`'s
  // docstring for why this replaced two separate client-side `/api/auth-config`
  // calls (one from `LayoutContent`, one from whichever consumer — the
  // landing page or `TermsAcceptanceGate` — was also mounted).
  const initialQuickStart = await fetchQuickStartEnabledServer();

  return (
    <html lang="en" suppressHydrationWarning data-theme-mode={storedThemeMode}>
      <head>
        {/*
          Plain inline script rather than `next/script` with
          `beforeInteractive`: that renders a `self.__next_s` push drained by
          the client bootstrap, which both logs a React 19 console error and
          gives up the guarantee that `__ENV__` exists before any client code
          reads it. Inline in <head> it is in the initial HTML.
        */}
        <script
          id="rhesis-runtime-env"
          dangerouslySetInnerHTML={{ __html: runtimeEnvScript }}
        />
        {/*
          Runs before first paint: when the visitor has made no explicit choice,
          resolve the mode from the browser instead of defaulting to light.
          `ThemeContextProvider` reads the attribute this sets, so the two agree
          and there is no flash.
        */}
        <script
          id="rhesis-theme-mode"
          dangerouslySetInnerHTML={{ __html: THEME_MODE_SCRIPT }}
        />
        <style
          id="rhesis-theme-mode-paint"
          dangerouslySetInnerHTML={{ __html: THEME_MODE_STYLE }}
        />
        {deploymentBranding.font?.source === 'google' && (
          <link
            rel="stylesheet"
            href={deploymentBranding.font.googleHref}
            crossOrigin="anonymous"
          />
        )}
        {deploymentBranding.font?.source === 'custom' && (
          <style
            id="rhesis-brand-font"
            dangerouslySetInnerHTML={{
              __html: buildFontFaceCss(deploymentBranding.font),
            }}
          />
        )}
      </head>
      <body suppressHydrationWarning>
        <ThemeContextProvider
          disableTransitionOnChange
          initialMode={storedThemeMode ?? 'light'}
          brandColors={{
            primary: deploymentBranding.primaryColor,
            secondary: deploymentBranding.secondaryColor,
            fontFamily: deploymentBranding.font?.family,
          }}
        >
          <LayoutContent
            session={session}
            navigation={navigation}
            branding={branding}
            authentication={AUTHENTICATION}
            initialActiveProject={initialActiveProject}
            initialProjects={initialProjects}
            initialUserSettings={initialUserSettings}
            initialOrganization={organization}
            initialQuickStart={initialQuickStart}
          >
            {props.children}
          </LayoutContent>
        </ThemeContextProvider>
      </body>
    </html>
  );
}
