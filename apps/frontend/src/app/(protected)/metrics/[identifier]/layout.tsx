import React from 'react';
import { Metadata } from 'next';

// This will be overridden by the dynamic generation in page.tsx
export const metadata: Metadata = {
  title: 'Metric Details',
};

interface MetricDetailLayoutProps {
  children: React.ReactNode;
}

export default function MetricDetailLayout({ children }: MetricDetailLayoutProps) {
  return children;
} 