import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ArchitectSession,
  ArchitectSessionCreateRequest,
} from '@/utils/api-client/architect-client';

export interface CreateAndOpenArchitectSessionOptions {
  sessionToken: string;
  title: string;
  initialMessage: string;
  /** Open in a new tab (default true). Falls back to same-tab if blocked. */
  newTab?: boolean;
  /** Test seams */
  openWindow?: (url?: string, target?: string) => Window | null;
  navigate?: (url: string) => void;
}

/**
 * Create an Architect session with an initial message already processing,
 * then navigate to `/architect?session=<id>`.
 *
 * Opens `about:blank` synchronously on the click gesture so browsers do not
 * popup-block the tab after the async create call (peqy / #2178).
 */
export async function createAndOpenArchitectSession(
  options: CreateAndOpenArchitectSessionOptions
): Promise<ArchitectSession> {
  const { sessionToken, title, initialMessage } = options;
  const newTab = options.newTab !== false;
  const openWindow =
    options.openWindow ??
    (typeof window !== 'undefined' ? window.open.bind(window) : undefined);
  const navigate =
    options.navigate ??
    (typeof window !== 'undefined'
      ? (url: string) => {
          window.location.assign(url);
        }
      : undefined);

  let tab: Window | null = null;
  if (newTab && openWindow) {
    tab = openWindow('about:blank', '_blank');
  }

  try {
    const client = new ApiClientFactory(sessionToken).getArchitectClient();
    const payload: ArchitectSessionCreateRequest = {
      title,
      initial_message: initialMessage,
    };
    const session = await client.createSession(payload);
    const url = `/architect?session=${encodeURIComponent(session.id)}`;

    if (tab && !tab.closed) {
      tab.location.href = url;
    } else if (navigate) {
      navigate(url);
    }

    return session;
  } catch (error) {
    if (tab && !tab.closed) {
      tab.close();
    }
    throw error;
  }
}
