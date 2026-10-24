import React from "react";

export default function StatCard({ icon: Icon, label, value, tone = "violet" }) {
  return (
    <div className="stat-card dashboard-stat-card">
      <div className={`stat-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </div>
      <div className="stat-info dashboard-stat-info">
        <span className="dashboard-stat-label">{label}</span>
        <strong className="dashboard-stat-value">{value}</strong>
      </div>
    </div>
  );
}
