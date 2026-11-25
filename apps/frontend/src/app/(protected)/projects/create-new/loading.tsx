import PageLoadingState from '@/components/common/PageLoadingState';
import DelayedReveal from '@/components/loading/DelayedReveal';

// Without this the Projects directory header would stand in for the wizard.
export default function CreateProjectLoading() {
  return (
    <DelayedReveal>
      <PageLoadingState />
    </DelayedReveal>
  );
}
