import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <ErrorBoundary>{children}</ErrorBoundary>
    </div>
  );
}
