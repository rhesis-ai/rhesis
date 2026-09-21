/**
 * Input affordances that are not a plain text box.
 *
 * The manifest says what is stored; it does not say what the user types into,
 * and it should not. Parsing a pasted GitHub URL into an owner and a repo is a
 * property of the form, not of the provider's API, so it lives here rather
 * than as provider-specific strings in the backend. Same reasoning as the
 * provider icons.
 *
 * Anything not listed here renders as a text field straight from
 * `manifest.fields`.
 */

import type { Tool } from '@/utils/api-client/interfaces/tool';

/** Normalize a URL to have a scheme, so `new URL()` can parse it. */
export function withScheme(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return '';
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

/**
 * A field whose single input maps to a nested metadata object.
 *
 * `toStored` returns null when the input cannot be parsed, which the form
 * reports using `invalidMessage` rather than sending something malformed.
 */
export interface MetadataAdapter {
  /** Metadata key this adapter owns, e.g. `repository`. */
  storedKey: string;
  /** Turn the saved tool back into what the user typed. */
  hydrate(tool: Tool): string;
  toStored(input: string): Record<string, unknown> | null;
  invalidMessage: string;
}

function parseRepositoryUrl(
  url: string
): { owner: string; repo: string; full_name: string } | null {
  const trimmed = url.trim();
  if (!trimmed) return null;

  const fullUrl = /(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/]+)/;
  const ownerRepo = /^([^/]+)\/([^/]+)$/;
  const match = trimmed.match(fullUrl) ?? trimmed.match(ownerRepo);
  if (!match) return null;

  const owner = match[1];
  const repo = match[2].replace(/\.git$/, '');
  // `full_name` is not a declared field: the backend never validates it, but
  // ConnectedToolCard reads it, so it has to survive a round trip.
  return { owner, repo, full_name: `${owner}/${repo}` };
}

function parseGitLabProject(url: string): { namespace: string } | null {
  const trimmed = url.trim();
  if (!trimmed) return null;

  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const path = new URL(withScheme(trimmed)).pathname.replace(
        /^\/+|\/+$/g,
        ''
      );
      // Everything before `/-/` is the project; the rest is a file or a view.
      const namespace = path.split('/-/')[0];
      return namespace.includes('/') ? { namespace } : null;
    } catch {
      return null;
    }
  }

  const path = trimmed.match(/^([^/\s]+\/[^/\s]+(?:\/[^/\s]+)*)$/);
  return path && path[1].includes('/') ? { namespace: path[1] } : null;
}

/** Keyed by `<provider>:<field key>`. */
export const METADATA_ADAPTERS: Record<string, MetadataAdapter> = {
  'github:repository.owner': {
    storedKey: 'repository',
    hydrate: tool => {
      const repo = tool.tool_metadata?.repository;
      return repo?.owner && repo?.repo
        ? `https://github.com/${repo.owner}/${repo.repo}`
        : '';
    },
    toStored: input => {
      const parsed = parseRepositoryUrl(input);
      return parsed ? { repository: parsed } : null;
    },
    invalidMessage:
      'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo',
  },
  'gitlab:project.namespace': {
    storedKey: 'project',
    hydrate: tool => {
      const project = tool.tool_metadata?.project;
      return typeof project === 'object' &&
        typeof project?.namespace === 'string'
        ? project.namespace
        : '';
    },
    toStored: input => {
      const parsed = parseGitLabProject(input);
      return parsed ? { project: parsed } : null;
    },
    invalidMessage:
      'Invalid project path. Please use format: group/project or https://gitlab.com/group/project',
  },
};

/**
 * Credential values the form rewrites before sending.
 *
 * Both accept something friendlier than what the API wants: a GitLab host
 * without its API path, or an Azure DevOps URL where an org name is asked for.
 */
export const CREDENTIAL_TRANSFORMS: Record<string, (value: string) => string> =
  {
    'gitlab:GITLAB_API_URL': value => {
      const url = withScheme(value).replace(/\/$/, '');
      if (!url) return '';
      return url.endsWith('/api/v4') ? url : `${url}/api/v4`;
    },
    'azure_devops:AZURE_DEVOPS_ORG': value => {
      const trimmed = value.trim().replace(/\/$/, '');
      const devAzure = trimmed.match(/dev\.azure\.com\/([^/?#]+)/i);
      if (devAzure) return devAzure[1];
      const visualStudio = trimmed.match(
        /(?:https?:\/\/)?([\w-]+)\.visualstudio\.com/i
      );
      if (visualStudio) return visualStudio[1];
      return trimmed;
    },
  };

/**
 * Fields rendered as a select rather than a text box, with the options coming
 * from the test-connection response.
 */
export const OPTION_FIELDS = new Set(['jira:space_key']);

export function adapterKey(provider: string, fieldKey: string): string {
  return `${provider}:${fieldKey}`;
}
