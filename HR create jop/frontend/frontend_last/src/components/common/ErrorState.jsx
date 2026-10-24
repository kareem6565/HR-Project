import React from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import Button from "./Button";

// Generic "the request failed" state with a retry action and accessible alert semantics (UI-01, UI-03).
// Usage: <ErrorState message="Unable to load candidates. Please try again." onRetry={load} />
export default function ErrorState({
  message = "Something went wrong. Please try again.",
  onRetry,
}) {
  return (
    <div className="error-state" role="alert" aria-live="assertive">
      <div className="error-state-icon" aria-hidden="true">
        <AlertTriangle size={22} />
      </div>
      <p>{message}</p>
      {onRetry && (
        <Button
          type="button"
          variant="primary"
          icon={RotateCw}
          onClick={onRetry}
          aria-label={`Try again: ${message}`}
        >
          Try Again
        </Button>
      )}
    </div>
  );
}
