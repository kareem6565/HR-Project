import React, { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar";
import Navbar from "../components/layout/Navbar";
import HERAChatbot from "../components/chatbot/HERAChatbot";

function takeWorkspaceEntryMotion(pathname) {
  if (pathname !== "/dashboard") return "";
  try {
    const entryMotion = sessionStorage.getItem("hera-workspace-entry-motion");
    if (entryMotion === "recruitment") sessionStorage.removeItem("hera-workspace-entry-motion");
    return entryMotion === "recruitment" ? entryMotion : "";
  } catch (_) {
    return "";
  }
}

export default function MainLayout() {
  const { pathname } = useLocation();
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const [workspaceEntryMotion, setWorkspaceEntryMotion] = useState(() => takeWorkspaceEntryMotion(pathname));

  useEffect(() => {
    setIsNavigationOpen(false);
    if (pathname !== "/dashboard") setWorkspaceEntryMotion("");
  }, [pathname]);

  useEffect(() => {
    if (!isNavigationOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") setIsNavigationOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isNavigationOpen]);

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
      <button
        className={`mobile-nav-backdrop ${isNavigationOpen ? "is-visible" : ""}`}
        type="button"
        aria-label="Close navigation menu"
        tabIndex={isNavigationOpen ? 0 : -1}
        onClick={() => setIsNavigationOpen(false)}
      />
      <Sidebar isOpen={isNavigationOpen} />
      <div className="main">
        <Navbar
          pathname={pathname}
          isNavigationOpen={isNavigationOpen}
          onMenuToggle={() => setIsNavigationOpen((open) => !open)}
        />
        <main className="page-content" id="main-content" tabIndex={-1}>
          <div key={pathname} className={`page-transition${workspaceEntryMotion ? ` page-transition--workspace-${workspaceEntryMotion}` : ""}`}>
            <Outlet />
          </div>
        </main>
        {isSchedulingPage && <HERAChatbot inline />}
      </div>
      {!isPrimaryScreeningOrReview && !isSchedulingPage && <HERAChatbot />}
    </div>
  );
}
