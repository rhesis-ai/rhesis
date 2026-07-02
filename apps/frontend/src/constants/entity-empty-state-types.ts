export interface EmptyStateAction {
  label: string;
  href?: string;
  onAction?: () => void;
  disabled?: boolean;
}

export interface EmptyStateArticle {
  href: string;
  title?: string;
  description?: string;
  imageUrl?: string;
}

export interface EmptyStateLinkCard {
  title: string;
  description: string;
  linkLabel: string;
  href?: string;
}

export interface EntityEmptyStateEnrichment {
  secondaryAction?: EmptyStateAction;
  media?: {
    youtubeVideoId?: string;
    youtubeUrl?: string;
    alt?: string;
  };
  helpArticles?: { title: string; items: EmptyStateArticle[] };
  communityLinks?: { title: string; items: EmptyStateLinkCard[] };
}

export type EntityEmptyStateKey =
  | 'projects'
  | 'tests'
  | 'test-sets'
  | 'test-runs'
  | 'endpoints'
  | 'behaviors'
  | 'metrics'
  | 'experiments';
