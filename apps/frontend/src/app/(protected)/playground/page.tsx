import { Metadata } from 'next';
import PlaygroundClient from './components/PlaygroundClient';

export const metadata: Metadata = {
  title: 'Playground',
};

export default function PlaygroundPage() {
  return <PlaygroundClient />;
}
