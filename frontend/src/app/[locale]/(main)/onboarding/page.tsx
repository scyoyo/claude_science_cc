import { WizardChat } from "@/components/wizard/WizardChat";

export default function OnboardingPage() {
  return (
    <div className="flex h-[calc(100dvh-72px)] sm:h-[calc(100vh-96px)] flex-col -m-3 sm:-m-6 min-h-0 w-full max-w-[100vw]">
      <WizardChat />
    </div>
  );
}
