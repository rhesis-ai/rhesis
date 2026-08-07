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
];

export const LOCAL_PROVIDERS = ['huggingface', 'lmformatenforcer', 'ollama'];

export const EMBEDDING_PROVIDERS = ['openai', 'gemini', 'vertex_ai'];

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
  modelType: 'language' | 'embedding'
): boolean {
  const listable =
    modelType === 'embedding'
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
};

// Providers where the API key is optional (proxy servers that may not require auth)
export const PROVIDERS_WITH_OPTIONAL_API_KEY = ['litellm_proxy'];

// Provider icon mapping
export const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  anthropic: <SiAnthropic className="h-8 w-8" />,
  cohere: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  gemini: <SiGoogle className="h-8 w-8" />,
  groq: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  huggingface: <SiHuggingface className="h-8 w-8" />,
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
