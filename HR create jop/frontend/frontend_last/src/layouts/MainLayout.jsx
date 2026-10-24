import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar";
import Navbar from "../components/layout/Navbar";
import HERAChatbot from "../components/chatbot/HERAChatbot";

export default function MainLayout() {
  const { pathname } = useLocation();

  // Keep the AI chatbot out of the primary screening and candidate review workflow
  // to avoid distracting or obstructing human decision-making and resume processing.
  const isPrimaryScreeningOrReview =
    pathname.startsWith("/candidates/screen") ||
    pathname.includes("/review") ||
    pathname.startsWith("/matching-results");
  const isSchedulingPage = pathname === "/interviews/schedule";

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>
      <Sidebar />
      <div className="main">
        <Navbar pathname={pathname} />
        <main className="page-content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        {isSchedulingPage && <HERAChatbot inline />}
      </div>
      {!isPrimaryScreeningOrReview && !isSchedulingPage && <HERAChatbot />}
    </div>
  );
}
