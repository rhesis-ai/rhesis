import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MCP',
};

export default function MCPLayout({ children }: { children: React.ReactNode }) {
  return children;
}
