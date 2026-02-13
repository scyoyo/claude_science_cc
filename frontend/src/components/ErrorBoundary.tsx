"use client";

import { Component, type ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="max-w-lg mx-auto mt-8">
          <Card className="border-destructive/50">
            <CardContent className="pt-6 space-y-4">
              <h2 className="text-lg font-semibold text-destructive">Something went wrong</h2>
              <p className="text-sm text-muted-foreground">{this.state.error?.message}</p>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => this.setState({ hasError: false, error: null })}
              >
                Try Again
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
