import React from 'react';
import {
  SiOpenai,
  SiGoogle,
  SiHuggingface,
  SiOllama,
  SiReplicate,
} from '@icons-pack/react-simple-icons';
import AnthropicIcon from '@mui/icons-material/Psychology';
import CohereLogo from '@mui/icons-material/AutoFixHigh';
import MistralIcon from '@mui/icons-material/AcUnit';
import SmartToyIcon from '@mui/icons-material/SmartToy';
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
// These must match the keys in PROVIDER_REGISTRY in sdk/src/rhesis/sdk/models/factory.py
export const SUPPORTED_PROVIDERS = ['openai', 'gemini', 'ollama'];

// Providers that require custom endpoint URLs (self-hosted or local)
export const PROVIDERS_REQUIRING_ENDPOINT = ['ollama', 'vllm', 'huggingface'];

// Default endpoints for providers that need them
export const DEFAULT_ENDPOINTS: Record<string, string> = {
  ollama: 'http://localhost:11434',
  vllm: 'http://localhost:8000',
};

// Provider icon mapping
export const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  anthropic: (
    <AnthropicIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
  ),
  cohere: <CohereLogo sx={{ fontSize: theme => theme.iconSizes.large }} />,
  gemini: <SiGoogle className="h-8 w-8" />,
  groq: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  huggingface: <SiHuggingface className="h-8 w-8" />,
  meta: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  mistral: <MistralIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  ollama: <SiOllama className="h-8 w-8" />,
  openai: <SiOpenai className="h-8 w-8" />,
  perplexity: (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
  ),
  replicate: <SiReplicate className="h-8 w-8" />,
  rhesis: (
    <Image
      src="/logos/rhesis-logo-favicon.svg"
      alt="Rhesis"
      width={32}
      height={32}
      style={{ width: '32px', height: '32px' }}
    />
  ),
  together: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
  vllm: <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />,
};

// Provider information interface
export interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}
