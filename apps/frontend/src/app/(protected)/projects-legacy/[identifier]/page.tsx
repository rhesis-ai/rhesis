import { auth } from '@/auth';
import ProjectDetails from '../components/ProjectDetails';

// This is temporary mock data until we have the backend
const mockProject = {
  id: '1',
  name: 'Financial Assistant',
  description: 'AI-powered platform for financial data retrieval, research, and analysis',
  environment: 'production',
  useCase: 'other',
  owner: {
    id: '12345678-1234-1234-1234-123456789012',
    name: 'Harry Cruz',
    email: 'harry.cruz@example.com',
    family_name: 'Cruz',
    given_name: 'Harry',
    picture: 'https://example.com/avatar2.png',
    organization_id: '12345678-1234-1234-1234-123456789012'
  },
  tags: ['finance', 'data-analysis', 'research', 'ai'],
  createdAt: '2024-03-15',
  user: {
    id: '12345678-1234-1234-1234-123456789012',
    name: 'John Doe',
    email: 'john.doe@example.com',
    family_name: 'Doe',
    given_name: 'John',
    picture: 'https://example.com/avatar.png',
    organization_id: '12345678-1234-1234-1234-123456789012'
  },
  organization: {
    id: '12345678-1234-1234-1234-123456789012',
    name: 'ACME Corp',
    description: 'A leading technology company',
    email: 'info@acme.com',
    user_id: '12345678-1234-1234-1234-123456789012'
  },
  system: {
    name: 'Financial Data Assistant',
    description: 'AI-powered financial research and analysis system',
    primary_goals: [
      'Provide users with accurate and up-to-date financial data',
      'Perform web research to gather supplementary information',
      'Summarize and present information in a clear and concise manner'
    ],
    key_capabilities: [
      'Retrieve financial data such as stock prices, company profiles, financial ratios, key metrics, and market capitalization',
      'Perform web scraping to extract relevant information from websites',
      'Summarize and synthesize information from various sources to generate coherent responses to user queries'
    ]
  },
  agents: [
    {
      name: 'Financial Data Agent',
      description: 'Handles financial data retrieval and processing',
      responsibilities: [
        'Fetch current stock prices using get_stock_price tool',
        'Retrieve company profiles using get_company_profile tool',
        'Get financial ratios using get_financial_ratios tool',
        'Access key metrics using get_key_metrics tool',
        'Retrieve market capitalization using get_market_cap tool',
        'Screen stocks using get_stock_screener tool'
      ]
    },
    {
      name: 'Research Agent',
      description: 'Conducts web research and information gathering',
      responsibilities: [
        'Perform web scraping to gather financial news',
        'Extract relevant information from financial websites',
        'Monitor market trends and updates',
        'Collect supplementary information from various sources'
      ]
    },
    {
      name: 'Analysis Agent',
      description: 'Analyzes and synthesizes financial information',
      responsibilities: [
        'Synthesize information from multiple sources',
        'Generate coherent responses to user queries',
        'Create summary reports of financial data',
        'Present information in a clear and concise manner'
      ]
    }
  ],
  requirements: [
    {
      name: 'Retrieve Current Stock Prices',
      description: 'The Financial_Data_Agent can fetch the current stock prices for a given symbol using the get_stock_price tool'
    },
    {
      name: 'Fetch Company Profiles',
      description: 'The Financial_Data_Agent can retrieve the company profile for a given symbol using the get_company_profile tool'
    },
    {
      name: 'Obtain Financial Ratios',
      description: 'The Financial_Data_Agent can fetch financial ratios for a given symbol using the get_financial_ratios tool'
    },
    {
      name: 'Access Key Metrics',
      description: 'The Financial_Data_Agent can retrieve key metrics for a given symbol using the get_key_metrics tool'
    },
    {
      name: 'Retrieve Market Capitalization',
      description: 'The Financial_Data_Agent can fetch the current market capitalization for a given symbol using the get_market_cap tool'
    },
    {
      name: 'Use Stock Screener',
      description: 'The Financial_Data_Agent can screen stocks based on various criteria using the get_stock_screener tool'
    }
  ],
  scenarios: [
    {
      name: 'Fetch Current Stock Price',
      description: 'User requests the current stock price of a specific company'
    },
    {
      name: 'Retrieve Company Profile',
      description: 'User requests the profile of a specific company'
    },
    {
      name: 'Get Financial Ratios',
      description: 'User requests financial ratios for a specific company, either annually or quarterly'
    },
    {
      name: 'Fetch Key Metrics',
      description: 'User requests key financial metrics for a specific company, either annually or quarterly'
    },
    {
      name: 'Retrieve Market Capitalization',
      description: 'User requests the current market capitalization of a specific company'
    },
    {
      name: 'Stock Screening',
      description: 'User defines screening criteria to find stocks that meet specific financial and market conditions'
    }
  ],
  personas: [
    {
      name: 'Retail Investor',
      description: 'An individual investor seeking basic information on stock prices, company profiles, and financial ratios to make informed investment decisions'
    },
    {
      name: 'Financial Analyst',
      description: 'A professional who requires detailed financial data, key metrics, and market capitalization information for in-depth analysis and reporting'
    },
    {
      name: 'Investment Manager',
      description: 'An individual managing a portfolio of investments who needs comprehensive financial data, market screening tools, and summarized reports to guide investment strategies'
    },
    {
      name: 'Economics Student',
      description: 'A learner seeking to understand financial concepts and data, relying on the system\'s ability to fetch and summarize information for educational purposes'
    },
    {
      name: 'Journalist',
      description: 'A reporter needing quick access to financial data and web-scraped information to support news articles and reports on market trends'
    },
    {
      name: 'Researcher',
      description: 'An academic or industry researcher looking for reliable financial data and web-scraped content to support research projects and publications'
    }
  ]
};

// Update the interface to match Next.js generated types
interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function ProjectPage({ params, searchParams }: PageProps) {
  const { identifier } = await params;
  
  return (
    <ProjectDetails 
      project={mockProject} 
      sessionToken="mock-token" 
    />
  );
} 