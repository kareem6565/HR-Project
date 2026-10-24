import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/common/ProtectedRoute";

import AuthLayout from "./layouts/AuthLayout";
import MainLayout from "./layouts/MainLayout";

import Login from "./pages/auth/Login";
import SsoCallback from "./pages/auth/SsoCallback";

import Dashboard from "./pages/dashboard/Dashboard";
import JobsList from "./pages/jobs/JobsList";
import JobDetails from "./pages/jobs/JobDetails";
import JobForm from "./pages/jobs/JobForm";
import CandidatesList from "./pages/candidates/CandidatesList";
import CandidateDetails from "./pages/candidates/CandidateDetails";
import ScreenCandidates from "./pages/candidates/ScreenCandidates";
import EvaluationsList from "./pages/evaluations/EvaluationsList";
import ApplicationsList from "./pages/applications/ApplicationsList";
import ApplicationReview from "./pages/review/ApplicationReview";
import TalentPoolList from "./pages/talent-pool/TalentPoolList";
import MatchingResults from "./pages/matching/MatchingResults";
import AnalyticsPage from "./pages/analytics/AnalyticsPage";
import AISettings from "./pages/settings/AISettings";
import InterviewsList from "./pages/interviews/InterviewsList";
import ScheduleInterview from "./pages/interviews/ScheduleInterview";
import InterviewFeedback from "./pages/interviews/InterviewFeedback";
import InterviewQuestions from "./pages/interview-questions/InterviewQuestions";
import QuestionSetBuilder from "./pages/interview-questions/QuestionSetBuilder";
import AIActivityList from "./pages/ai-activity/AIActivityList";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Authentication flow */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route path="/sso/callback" element={<SsoCallback />} />

          {/* Legacy identity route redirected */}
          <Route path="/identity" element={<Navigate to="/dashboard" replace />} />

          {/* Protected app routes */}
          <Route
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />

            <Route path="/jobs" element={<JobsList />} />
            <Route path="/jobs/new" element={<JobForm />} />
            <Route path="/jobs/:id/edit" element={<JobForm />} />
            <Route path="/jobs/:id" element={<JobDetails />} />

            <Route path="/candidates" element={<CandidatesList />} />
            <Route path="/candidates/screen" element={<ScreenCandidates />} />
            <Route path="/candidates/:id" element={<CandidateDetails />} />

            <Route path="/evaluations" element={<EvaluationsList />} />

            <Route path="/applications" element={<ApplicationsList />} />
            <Route path="/applications/:id/review" element={<ApplicationReview />} />
            <Route path="/applications/:id/questions" element={<QuestionSetBuilder />} />

            <Route path="/talent-pool" element={<TalentPoolList />} />
            <Route path="/matching-results" element={<MatchingResults />} />
            <Route path="/matching" element={<MatchingResults />} />
            <Route path="/analytics" element={<AnalyticsPage />} />

            {/* Admin-only settings route */}
            <Route
              path="/settings"
              element={
                <ProtectedRoute allowedRoles={["admin", "administrator"]}>
                  <AISettings />
                </ProtectedRoute>
              }
            />

            <Route path="/interviews" element={<InterviewsList />} />
            <Route path="/interviews/schedule" element={<ScheduleInterview />} />
            <Route path="/interviews/:id/feedback" element={<InterviewFeedback />} />
            <Route path="/interview-questions" element={<InterviewQuestions />} />
            <Route path="/ai-activity" element={<AIActivityList />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
