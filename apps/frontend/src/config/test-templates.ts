import ShieldIcon from '@mui/icons-material/Shield';
import GavelIcon from '@mui/icons-material/Gavel';
import SpeedIcon from '@mui/icons-material/Speed';
import PsychologyIcon from '@mui/icons-material/Psychology';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import SecurityIcon from '@mui/icons-material/Security';
import AccessibilityNewIcon from '@mui/icons-material/AccessibilityNew';
import LanguageIcon from '@mui/icons-material/Language';
import PrivacyTipIcon from '@mui/icons-material/PrivacyTip';
import BalanceIcon from '@mui/icons-material/Balance';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import { TestTemplate } from '@/app/(protected)/tests/new-generated/components/shared/types';

// Icon mapping
const iconMap: Record<string, React.ComponentType<any>> = {
  ShieldIcon,
  BalanceIcon,
  SpeedIcon,
  PsychologyIcon,
  HealthAndSafetyIcon,
  AccountBalanceIcon,
  SecurityIcon,
  AccessibilityNewIcon,
  LanguageIcon,
  VerifiedUserIcon,
  GavelIcon,
  PrivacyTipIcon,
};

// Template library with 12 predefined templates
export const TEMPLATES: TestTemplate[] = [
  {
    id: 'gdpr-compliance',
    name: 'GDPR Compliance',
    description: 'Test privacy and data protection compliance',
    icon: ShieldIcon,
    color: 'primary.main',
    behaviors: ['Compliance', 'Privacy'],
    topics: ['GDPR', 'Data Protection', 'User Rights'],
    category: ['Legal', 'Privacy'],
    popularity: 'high',
  },
  {
    id: 'bias-detection',
    name: 'Bias Detection',
    description: 'Identify and test for AI biases',
    icon: BalanceIcon,
    color: 'secondary.main',
    behaviors: ['Fairness', 'Reliability'],
    topics: ['Bias', 'Fairness', 'Demographics'],
    category: ['Ethics', 'Quality'],
    popularity: 'high',
  },
  {
    id: 'performance-testing',
    name: 'Performance Testing',
    description: 'Test response quality and latency',
    icon: SpeedIcon,
    color: 'warning.main',
    behaviors: ['Reliability', 'Performance'],
    topics: ['Speed', 'Quality', 'Consistency'],
    category: ['Performance', 'Quality'],
    popularity: 'high',
  },
  {
    id: 'hallucination-detection',
    name: 'Hallucination Detection',
    description: 'Detect factual inaccuracies',
    icon: PsychologyIcon,
    color: 'error.main',
    behaviors: ['Reliability', 'Accuracy'],
    topics: ['Facts', 'Accuracy', 'Verification'],
    category: ['Quality', 'Reliability'],
    popularity: 'medium',
  },
  {
    id: 'medical-safety',
    name: 'Medical Safety',
    description: 'Test healthcare AI applications',
    icon: HealthAndSafetyIcon,
    color: 'success.main',
    behaviors: ['Safety', 'Compliance'],
    topics: ['Medical', 'Safety', 'HIPAA'],
    category: ['Healthcare', 'Safety'],
    popularity: 'medium',
  },
  {
    id: 'financial-compliance',
    name: 'Financial Compliance',
    description: 'Test financial service regulations',
    icon: AccountBalanceIcon,
    color: 'info.main',
    behaviors: ['Compliance', 'Security'],
    topics: ['Financial', 'Regulations', 'Security'],
    category: ['Finance', 'Legal'],
    popularity: 'medium',
  },
  {
    id: 'security-testing',
    name: 'Security Testing',
    description: 'Test for security vulnerabilities',
    icon: SecurityIcon,
    color: 'error.dark',
    behaviors: ['Security', 'Reliability'],
    topics: ['Security', 'Vulnerabilities', 'Attacks'],
    category: ['Security', 'Testing'],
    popularity: 'high',
  },
  {
    id: 'accessibility',
    name: 'Accessibility',
    description: 'Test for accessibility compliance',
    icon: AccessibilityNewIcon,
    color: 'warning.dark',
    behaviors: ['Accessibility', 'Compliance'],
    topics: ['Accessibility', 'WCAG', 'Inclusivity'],
    category: ['Accessibility', 'Legal'],
    popularity: 'low',
  },
  {
    id: 'multilingual',
    name: 'Multilingual',
    description: 'Test language understanding',
    icon: LanguageIcon,
    color: 'secondary.main',
    behaviors: ['Reliability', 'Quality'],
    topics: ['Languages', 'Translation', 'Localization'],
    category: ['Localization', 'Quality'],
    popularity: 'medium',
  },
  {
    id: 'content-moderation',
    name: 'Content Moderation',
    description: 'Test content filtering and safety',
    icon: VerifiedUserIcon,
    color: 'info.dark',
    behaviors: ['Safety', 'Compliance'],
    topics: ['Content', 'Moderation', 'Safety'],
    category: ['Safety', 'Content'],
    popularity: 'medium',
  },
  {
    id: 'legal-compliance',
    name: 'Legal Compliance',
    description: 'Test legal and regulatory compliance',
    icon: GavelIcon,
    color: 'primary.dark',
    behaviors: ['Compliance', 'Legal'],
    topics: ['Legal', 'Regulations', 'Policies'],
    category: ['Legal', 'Compliance'],
    popularity: 'medium',
  },
  {
    id: 'privacy-protection',
    name: 'Privacy Protection',
    description: 'Test data privacy measures',
    icon: PrivacyTipIcon,
    color: 'info.main',
    behaviors: ['Privacy', 'Security'],
    topics: ['Privacy', 'Data Protection', 'Encryption'],
    category: ['Privacy', 'Security'],
    popularity: 'high',
  },
];
