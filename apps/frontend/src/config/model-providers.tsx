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
  vllm: 'http://localhost:8000',
  litellm_proxy: 'http://0.0.0.0:4000',
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
      width={32}
      height={32}
      style={{ width: '32px', height: '32px' }}
    />
  ),
  replicate: <SiReplicate className="h-8 w-8" />,
  rhesis: (
    <Image
      src="/logos/rhesis-logo-favicon-transparent.svg"
      alt="Rhesis"
      width={32}
      height={32}
      style={{ width: '32px', height: '32px' }}
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

// Provider information interface
export interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}
