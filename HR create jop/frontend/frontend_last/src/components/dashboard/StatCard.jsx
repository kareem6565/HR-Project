import React from "react";
import useCountUp from "../../hooks/useCountUp";

export default function StatCard({ icon: Icon, label, value, tone = "violet", style }) {
  const numeric = typeof value === "number" && Number.isFinite(value);
  const display = useCountUp(value);
  return (
    <div className="stat-card dashboard-stat-card motion-card" style={style}>
      <div className={`stat-icon tone-${tone}`} aria-hidden="true">
        <Icon size={19} />
      </div>
      <div className="stat-info dashboard-stat-info">
        <span className="dashboard-stat-label">{label}</span>
        <strong
          className="dashboard-stat-value"
          aria-label={numeric ? String(value) : undefined}
        >
          {display}
        </strong>
      </div>
    </div>
  );
}
