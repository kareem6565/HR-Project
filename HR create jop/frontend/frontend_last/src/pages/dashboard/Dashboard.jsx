import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, ClipboardList, Plus, Users, UserRoundCheck } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import StatCard from "../../components/dashboard/StatCard";
import HeraAssistantMark from "../../components/common/HeraAssistantMark";
import ErrorState from "../../components/common/ErrorState";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import {
  getApplicationsByJob,
  getDashboardStats,
} from "../../services/dashboardService";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [applicationsByJob, setApplicationsByJob] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    let active = true;
    setLoading(true);
    setError(false);
    (async () => {
      try {
        const [nextStats, nextApplications] = await Promise.all([
          getDashboardStats(),
          getApplicationsByJob(),
        ]);
        if (!active) return;
        setStats(nextStats);
        setApplicationsByJob(nextApplications);
        setLoading(false);
      } catch {
        if (!active) return;
        setError(true);
        setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  };

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <LoadingSpinner label="Loading recruitment overview…" />;
  if (error) {
    return <ErrorState message="Unable to load the recruitment overview. Please try again." onRetry={load} />;
  }

  const hasApplications = stats.applications > 0;

  return (
    <div className="dashboard dashboard-redesign">
      <section className="dashboard-intro" aria-labelledby="dashboard-intro-title">
        <div className="dashboard-intro-copy">
          <p className="dashboard-kicker">
            <HeraAssistantMark size={25} />
            <span>HERA · AI-ASSISTED, HR-LED</span>
          </p>
          <h2 id="dashboard-intro-title">A clearer view of your hiring activity</h2>
          <p>Live totals from your current jobs and applications.</p>
        </div>
        <div className="dashboard-intro-actions">
          <span className="dashboard-live-indicator"><span aria-hidden="true" />Live workspace snapshot</span>
          <div className="dashboard-shortcuts" aria-label="Quick actions">
            <Link className="btn btn-primary dashboard-action-primary" to="/jobs/new">
              <Plus size={16} aria-hidden="true" /> Create vacancy
            </Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/applications">
              Review applications <ArrowRight size={15} aria-hidden="true" />
            </Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/applications">Applications</Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/jobs">
              Manage jobs <BriefcaseBusiness size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section className="stats-grid dashboard-stats" aria-label="Recruitment summary">
        <StatCard icon={Users} label="Candidates with applications" value={stats.candidatesWithApplications} />
        <StatCard icon={BriefcaseBusiness} label="Active jobs" value={stats.activeJobs} />
        <StatCard icon={ClipboardList} label="Applications" value={stats.applications} />
        <StatCard icon={UserRoundCheck} label="Advanced applications" value={stats.advancedApplications} />
      </section>

      {stats.totalJobs === 0 && stats.applications === 0 && (
        <section className="dashboard-empty panel" aria-label="No recruitment records">
          <div className="dashboard-empty-mark" aria-hidden="true"><BriefcaseBusiness size={20} /></div>
          <div>
            <h3>No recruitment records in this workspace yet</h3>
            <p>Create a vacancy to start. You can then review candidates and evaluate applications from this organization.</p>
            <div className="dashboard-shortcuts">
              <Link className="btn btn-primary" to="/jobs/new">Create a vacancy</Link>
              <Link className="btn btn-secondary" to="/candidates">Review candidates</Link>
              <Link className="btn btn-secondary" to="/applications">Open applications</Link>
            </div>
          </div>
        </section>
      )}

      <section className="dashboard-section" aria-labelledby="pipeline-title">
        <div className="dashboard-section-heading">
          <div>
            <h2 id="pipeline-title">Hiring activity</h2>
            <p>All recorded applications grouped by role.</p>
          </div>
          <span className="dashboard-section-note">Workspace snapshot · all recorded applications</span>
        </div>

        {hasApplications ? (
          <div className="charts-grid dashboard-charts dashboard-charts-overview">
            <section className="panel chart-panel dashboard-chart-panel" aria-labelledby="jobs-chart-title">
              <div className="dashboard-chart-heading">
                <div>
                  <h3 id="jobs-chart-title">Applications by job</h3>
                  <p>Compare application volume across open and past roles.</p>
                </div>
                <span className="dashboard-chart-total">
                  <strong>{stats.applications}</strong>
                  <span>applications</span>
                </span>
              </div>
              {applicationsByJob.length ? (
                <>
                <div
                  className="dashboard-chart"
                  role="img"
                  aria-label="Bar chart of applications for each job"
                  style={{ "--dashboard-chart-height": `${Math.min(Math.max(applicationsByJob.length * 48 + 72, 250), 430)}px` }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={applicationsByJob}
                      layout="vertical"
                      margin={{ top: 8, right: 18, left: 8, bottom: 8 }}
                      barCategoryGap="34%"
                    >
                      <CartesianGrid stroke="var(--hera-border)" horizontal={false} />
                      <XAxis
                        type="number"
                        allowDecimals={false}
                        tick={{ fill: "var(--hera-muted)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="job"
                        width={170}
                        tick={{ fill: "var(--hera-ink)", fontSize: 12 }}
                        tickFormatter={formatJobTick}
                        axisLine={false}
                        tickLine={false}
                        interval={0}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(27, 58, 58, 0.05)" }}
                        contentStyle={{ border: "1px solid var(--hera-border)", borderRadius: 10, boxShadow: "0 8px 24px rgba(16, 38, 35, .12)" }}
                      />
                      <Bar dataKey="applications" name="Applications" fill="var(--hera-teal)" radius={[0, 5, 5, 0]} maxBarSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <table className="sr-only">
                  <caption>Application counts by job</caption>
                  <thead><tr><th scope="col">Job</th><th scope="col">Applications</th></tr></thead>
                  <tbody>
                    {applicationsByJob.map((item) => (
                      <tr key={item.job}><th scope="row">{item.job}</th><td>{item.applications}</td></tr>
                    ))}
                  </tbody>
                </table>
                </>
              ) : <p className="dashboard-chart-empty">No job application breakdown is available yet.</p>}
            </section>

          </div>
        ) : stats.totalJobs > 0 ? (
          <div className="dashboard-empty panel">
            <div className="dashboard-empty-mark" aria-hidden="true"><BriefcaseBusiness size={20} /></div>
            <div>
              <h3>No applications yet</h3>
              <p>When candidates apply to your jobs, their real application activity will appear here.</p>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function formatJobTick(label) {
  return label.length > 25 ? `${label.slice(0, 22)}…` : label;
}
