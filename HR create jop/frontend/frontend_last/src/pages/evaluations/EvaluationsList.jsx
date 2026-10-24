import React from "react";
import { Navigate } from "react-router-dom";

// Keep old bookmarks working while sending recruiters to the application-level
// queue, where each AI evaluation belongs to a specific job application.
export default function EvaluationsList() {
  return <Navigate to="/applications" replace />;
}
