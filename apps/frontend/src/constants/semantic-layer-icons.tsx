import SmartToyIcon from '@mui/icons-material/SmartToy';
import BuildIcon from '@mui/icons-material/Build';
import SearchIcon from '@mui/icons-material/Search';
import ExtensionIcon from '@mui/icons-material/Extension';
import FunctionsIcon from '@mui/icons-material/Functions';
import StorageIcon from '@mui/icons-material/Storage';
import HttpIcon from '@mui/icons-material/Http';
import CodeIcon from '@mui/icons-material/Code';

/**
 * Semantic Layer Icon Mapping
 * Maps span name patterns to Material-UI icons
 * Based on Rhesis AI Semantic Layer specification
 */
export const SEMANTIC_LAYER_ICONS = {
  // AI Operations (from semantic layer)
  'ai.llm.invoke': SmartToyIcon, // LLM invocations
  'ai.tool.invoke': BuildIcon, // Tool/function calls
  'ai.retrieval': SearchIcon, // Vector store queries
  'ai.embedding': ExtensionIcon, // Embedding generation

  // Common patterns
  'function.': FunctionsIcon, // Generic function calls
  'db.': StorageIcon, // Database operations
  'http.': HttpIcon, // HTTP requests

  // Default
  default: CodeIcon, // Fallback icon
} as const;

/**
 * Semantic Layer Color Mapping
 * Maps span types to vibrant, theme-compatible colors
 * Uses MUI color palette for better theme integration
 */
export const SEMANTIC_LAYER_COLORS = {
  'ai.llm.invoke': 'success.main', // Green - AI/LLM (vibrant)
  'ai.tool.invoke': 'warning.main', // Orange - Tools (vibrant)
  'ai.retrieval': 'info.main', // Blue - Search/Retrieval (vibrant)
  'ai.embedding': 'secondary.main', // Purple - Embeddings (vibrant)
  'function.': 'primary.main', // Primary Blue - Functions (vibrant)
  'db.': 'warning.dark', // Dark Orange - Database (distinct from tools)
  'http.': 'secondary.light', // Light Purple - HTTP (distinct from embeddings)
  error: 'error.main', // Red - Errors (theme-aware)
  default: 'text.secondary', // Grey - Default (theme-aware)
} as const;
