import { Metadata } from 'next';
import ArchitectClient from './components/ArchitectClient';

export const metadata: Metadata = {
  title: 'Architect',
};

export default function ArchitectPage() {
  return <ArchitectClient />;
}
