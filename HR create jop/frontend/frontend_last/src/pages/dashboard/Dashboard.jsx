import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, ClipboardList, Users, UserRoundCheck } from "lucide-react";
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
        <div>
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
            <Link className="btn btn-primary" to="/applications">
              Review applications <ArrowRight size={15} aria-hidden="true" />
            </Link>
            <Link className="btn btn-secondary" to="/jobs">
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

      <section className="dashboard-section" aria-labelledby="pipeline-title">
        <div className="dashboard-section-heading">
          <div>
            <h2 id="pipeline-title">Hiring activity</h2>
            <p>All recorded applications grouped by role.</p>
          </div>
          <span>Workspace snapshot · all recorded applications</span>
        </div>

        {hasApplications ? (
          <div className="charts-grid dashboard-charts dashboard-charts-overview">
            <section className="panel chart-panel dashboard-chart-panel" aria-labelledby="jobs-chart-title">
              <div className="dashboard-chart-heading">
                <div>
                  <h3 id="jobs-chart-title">Applications by job</h3>
                  <p>Compare application volume across open and past roles.</p>
                </div>
              </div>
              {applicationsByJob.length ? (
                <div className="dashboard-chart" role="img" aria-label="Bar chart of applications for each job">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={applicationsByJob} margin={{ top: 12, right: 8, left: -18, bottom: 8 }}>
                      <CartesianGrid stroke="var(--hera-border)" vertical={false} />
                      <XAxis dataKey="job" tick={{ fill: "var(--hera-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis allowDecimals={false} tick={{ fill: "var(--hera-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: "rgba(27, 58, 58, 0.05)" }} />
                      <Bar dataKey="applications" name="Applications" fill="var(--hera-teal)" radius={[5, 5, 0, 0]} maxBarSize={48} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <p className="dashboard-chart-empty">No job application breakdown is available yet.</p>}
            </section>

          </div>
        ) : (
          <div className="dashboard-empty panel">
            <div className="dashboard-empty-mark" aria-hidden="true"><BriefcaseBusiness size={20} /></div>
            <div>
              <h3>No applications yet</h3>
              <p>When candidates apply to your jobs, their real application activity will appear here.</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
