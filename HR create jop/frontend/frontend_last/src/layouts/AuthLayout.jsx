import React from "react";
import { Outlet } from "react-router-dom";
import BrandIcon from "../components/common/BrandIcon";

export default function AuthLayout() {
  return (
    <div className="auth-shell">
      <div className="auth-side">
        <div className="brand">
          <div className="brand-icon">
            <BrandIcon size={20} />
          </div>
          <div>
            <strong>HERA</strong>
            <span>Recruitment System</span>
          </div>
        </div>
        <h2>Hire the right people, faster.</h2>
        <p>
          Manage jobs, screen candidates with AI, and review evaluations —
          all in one dashboard.
        </p>
      </div>
      <div className="auth-card-wrap">
        <Outlet />
      </div>
    </div>
  );
}
