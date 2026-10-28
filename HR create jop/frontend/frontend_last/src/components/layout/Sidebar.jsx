import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  BriefcaseBusiness,
  FileUp,
  ListOrdered,
  Users,
  ClipboardList,
  CalendarClock,
  Star,
  BarChart3,
  Settings,
} from "lucide-react";
import BrandIcon from "../common/BrandIcon";
import { BRAND } from "../../config/brand";
import useAuth from "../../hooks/useAuth";

// Core MVP recruiting workflow
const PRIMARY_NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { to: "/candidates/screen", label: "Screening", icon: FileUp },
  { to: "/matching-results", label: "Matching Results", icon: ListOrdered },
  { to: "/candidates", label: "Candidates", icon: Users },
  { to: "/applications", label: "Applications", icon: ClipboardList },
];

// Secondary operations and pipeline tools
const SECONDARY_NAV_ITEMS = [
  { to: "/interviews", label: "Interviews", icon: CalendarClock },
  { to: "/talent-pool", label: "Talent Pool", icon: Star },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

// Administrator-only configuration and observability
const ADMIN_NAV_ITEMS = [
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const { isAdmin } = useAuth();

  return (
    <aside className="sidebar" aria-label="Sidebar navigation">
      <div className="brand">
        <div className="brand-icon">
          <BrandIcon size={20} />
        </div>
        <div>
          <strong>{BRAND.name}</strong>
          <span>{BRAND.tagline}</span>
        </div>
      </div>

      <nav aria-label="Main navigation">
        <div className="nav-section" role="group" aria-label="Primary workflow">
          {PRIMARY_NAV_ITEMS.map(({ to, label, icon: Icon, badge }) => (
            <NavLink
              key={to}
              to={to}
              end
              title={label}
              aria-label={label}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
              {badge ? <span className="nav-badge">{badge}</span> : null}
            </NavLink>
          ))}
        </div>

        <div className="nav-section" role="group" aria-label="Secondary tools">
          <div className="nav-section-title" aria-hidden="true">
            Operations
          </div>
          {SECONDARY_NAV_ITEMS.map(({ to, label, icon: Icon, badge }) => (
            <NavLink
              key={to}
              to={to}
              end
              title={label}
              aria-label={label}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
              {badge ? <span className="nav-badge">{badge}</span> : null}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="sidebar-bottom">
        {isAdmin && (
          <div className="nav-section sidebar-admin-section" role="group" aria-label="Administration">
            <div className="nav-section-title" aria-hidden="true">
              Admin
            </div>
            {ADMIN_NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end
                title={label}
                aria-label={label}
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              >
                <Icon size={19} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
        )}
        <div className="powered">{BRAND.powered}</div>
      </div>
    </aside>
  );
}
