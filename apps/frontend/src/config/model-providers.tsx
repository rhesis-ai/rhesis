import React from 'react';
import {
  SiAnthropic,
  SiGoogle,
  SiHuggingface,
  SiMeta,
  SiMistralai,
  SiOllama,
  SiOpenrouter,
  SiPerplexity,
  SiReplicate,
} from '@icons-pack/react-simple-icons';
import CloudIcon from '@mui/icons-material/Cloud';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import HubIcon from '@mui/icons-material/Hub';
import Image from 'next/image';
import { MODEL_TYPES, type ModelType } from '@/constants/model-types';

/**
 * Model Provider Configuration
 *
 * This file contains all configuration related to model providers including:
 * - Supported providers (aligned with SDK)
 * - Provider icons and branding
 * - Endpoint requirements and defaults
 */

// Providers currently supported by the Rhesis SDK
// These must match the keys in LANGUAGE_MODEL_PROVIDER_REGISTRY in sdk/src/rhesis/sdk/models/factory.py
export const SUPPORTED_PROVIDERS = [
  'openai',
  'gemini',
  'vertex_ai',
  'ollama',
  'vllm',
  'anthropic',
  'groq',
  'mistral',
  'openrouter',
  'replicate',
  'perplexity',
  'polyphemus',
  'together_ai',
  'cohere',
  'huggingface',
  'lmformatenforcer',
  'meta_llama',
  'litellm_proxy',
  'azure_ai',
  'azure',
  'jev',
];

export const LOCAL_PROVIDERS = ['huggingface', 'lmformatenforcer', 'ollama'];

export const EMBEDDING_PROVIDERS = ['openai', 'gemini', 'vertex_ai'];

// Providers whose models answer typed questions but can't generate text. They are
// saved with model_type 'decision' and may only judge categorical metrics.
export const DECISION_PROVIDERS: readonly string[] = ['jev'];

export function isDecisionProvider(provider: string | undefined): boolean {
  return !!provider && DECISION_PROVIDERS.includes(provider);
}

// Providers that support GET /models/provider/{name} model listing.
// Keep aligned with _LISTABLE_LLM_PROVIDERS and _LISTABLE_EMBEDDING_PROVIDERS in
// sdk/src/rhesis/sdk/models/factory.py
export const LANGUAGE_MODEL_LISTABLE_PROVIDERS = [
  'anthropic',
  'azure',
  'azure_ai',
  'cohere',
  'gemini',
  'groq',
  'meta_llama',
  'mistral',
  'ollama',
  'openai',
  'openrouter',
  'perplexity',
  'replicate',
  'together_ai',
  'vertex_ai',
] as const;

export const EMBEDDING_MODEL_LISTABLE_PROVIDERS = [
  'openai',
  'gemini',
  'vertex_ai',
] as const;

export function providerSupportsModelListing(
  provider: string,
  modelType: ModelType
): boolean {
  if (modelType === MODEL_TYPES.DECISION) return false;
  const listable =
    modelType === MODEL_TYPES.EMBEDDING
      ? EMBEDDING_MODEL_LISTABLE_PROVIDERS
      : LANGUAGE_MODEL_LISTABLE_PROVIDERS;
  return (listable as readonly string[]).includes(provider);
}

// Providers that require custom endpoint URLs (self-hosted or local)
export const PROVIDERS_REQUIRING_ENDPOINT = [
  'ollama',
  'vllm',
  'huggingface',
  'lmformatenforcer',
  'litellm_proxy',
  'azure_ai',
  'azure',
];

// Default endpoints for providers that need them
export const DEFAULT_ENDPOINTS: Record<string, string> = {
  ollama: 'http://host.docker.internal:11434',
  vllm: 'http://host.docker.internal:8000',
  litellm_proxy: 'http://host.docker.internal:4000',
  jev: 'https://api.typesafe.ai',
};

// Providers with a default endpoint the SDK falls back to; the field is shown but may be left empty
export const PROVIDERS_WITH_OPTIONAL_ENDPOINT = ['jev'];

// Model names prefilled for providers that can't list their models
export const DEFAULT_MODEL_NAMES: Record<string, string> = {
  jev: 'jev-latest',
};

// Providers where the API key is optional (proxy servers that may not require auth)
export const PROVIDERS_WITH_OPTIONAL_API_KEY = ['litellm_proxy'];

/**
 * TypeSafe AI's mark for Jev, drawn here because `react-simple-icons` has none.
 * Sized like the Simple Icons (24px default) and filled with currentColor so it
 * matches the monochrome icons around it.
 */
function JevIcon({ size = 24 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 16.487 24"
      width={size}
      height={size}
      role="img"
      aria-label="Jev"
      xmlns="http://www.w3.org/2000/svg"
      className="h-8 w-8"
    >
      <path
        fill="currentColor"
        fillRule="evenodd"
        d="M 12.756 2.928 L 12.756 7.067 L 16.486 9.487 L 16.487 18.652 L 8.244 24 L 3.732 21.073 L 3.732 16.82 L 0 14.399 L 0 5.35 L 0.355 5.118 L 8.244 0 Z M 5.94 20.65 L 8.242 22.144 L 14.275 18.227 L 11.975 16.735 Z M 9.022 10.332 L 9.022 14.4 L 5.29 16.822 L 5.29 19.216 L 11.197 15.383 L 11.197 8.921 Z M 12.756 15.384 L 14.928 16.794 L 14.928 10.332 L 12.756 8.922 Z M 2.21 13.976 L 4.511 15.47 L 6.812 13.976 L 4.512 12.485 Z M 1.559 6.193 L 1.559 12.544 L 3.731 11.134 L 3.731 7.066 L 7.464 4.643 L 7.464 2.36 L 1.56 6.193 Z M 5.291 11.132 L 7.463 12.542 L 7.463 10.332 L 5.292 8.921 L 5.292 11.132 Z M 5.94 7.487 L 8.244 8.981 L 10.544 7.488 L 8.244 5.994 Z M 9.024 4.643 L 11.196 6.054 L 11.196 3.774 L 9.024 2.359 Z"
      />
    </svg>
  );
}

// Provider icon mapping
export const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  anthropic: <SiAnthropic className="h-8 w-8" />,
  cohere: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  gemini: <SiGoogle className="h-8 w-8" />,
  groq: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  huggingface: <SiHuggingface className="h-8 w-8" />,
  jev: <JevIcon />,
  lmformatenforcer: <SiHuggingface className="h-8 w-8" />,
  meta_llama: <SiMeta className="h-8 w-8" />,
  mistral: <SiMistralai className="h-8 w-8" />,
  ollama: <SiOllama className="h-8 w-8" />,
  openai: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  openrouter: <SiOpenrouter className="h-8 w-8" />,
  perplexity: <SiPerplexity className="h-8 w-8" />,
  polyphemus: (
    <Image
      src="/logos/polyphemus-logo-favicon-transparent.svg"
      alt="Polyphemus"
      width={20}
      height={20}
    />
  ),
  replicate: <SiReplicate className="h-8 w-8" />,
  rhesis: (
    <Image
      src="/logos/rhesis-logo-favicon-transparent.svg"
      alt="Rhesis"
      width={20}
      height={20}
    />
  ),
  together_ai: (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
  ),
  vertex_ai: <SiGoogle className="h-8 w-8" />,
  vllm: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  litellm_proxy: <HubIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  azure_ai: <CloudIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  azure: <CloudIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
};

// User-facing display names keyed by provider type_value. Overrides the
// backend-provided description where the stored text uses outdated branding
// (e.g. "Azure AI Studio" was renamed by Microsoft to "Azure AI Foundry").
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  azure_ai: 'Azure AI Foundry',
  azure: 'Azure OpenAI',
  jev: 'Jev (TypeSafe AI)',
};

// Resolve the label to show for a provider: display-name override first, then
// the backend description, then the raw type_value as a last resort.
export function getProviderDisplayName(provider: {
  type_value: string;
  description?: string;
}): string {
  return (
    PROVIDER_DISPLAY_NAMES[provider.type_value] ||
    provider.description ||
    provider.type_value
  );
}

// Provider information interface
export interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}
