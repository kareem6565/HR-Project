import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BriefcaseBusiness, ClipboardList, Plus, Sparkles, Users, UserRoundCheck } from "lucide-react";
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
  const topApplicationJob = applicationsByJob.reduce(
    (top, item) => (!top || item.applications > top.applications ? item : top),
    null,
  );
  const topJobShare = topApplicationJob && stats.applications
    ? Math.round((topApplicationJob.applications / stats.applications) * 100)
    : 0;

  return (
    <div className="dashboard dashboard-redesign motion-rise">
      <section className="dashboard-intro dashboard-intro--alive" aria-labelledby="dashboard-intro-title">
        <div className="hero-aurora" aria-hidden="true">
          <div className="blob b1" />
          <div className="blob b2" />
          <div className="blob b3" />
        </div>
        <div className="dashboard-intro-copy">
          <p className="dashboard-kicker">
            <HeraAssistantMark size={25} />
            <span>HERA · AI-ASSISTED, HR-LED</span>
          </p>
          <h2 id="dashboard-intro-title">A clearer view of your hiring activity</h2>
          <p>Live totals from your current jobs and applications.</p>
        </div>
        <div className="dashboard-intro-actions">
          <span className="dashboard-live-indicator"><span className="motion-live-dot" aria-hidden="true" />Live workspace snapshot</span>
          <div className="dashboard-shortcuts" aria-label="Quick actions">
            <Link className="btn btn-primary dashboard-action-primary" to="/jobs/new">
              <Plus size={16} aria-hidden="true" /> Create vacancy
            </Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/applications">
              Review applications <ArrowRight size={15} aria-hidden="true" />
            </Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/evaluations">Evaluations</Link>
            <Link className="btn btn-secondary dashboard-action-secondary" to="/jobs">
              Manage jobs <BriefcaseBusiness size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section className="stats-grid dashboard-stats" aria-label="Recruitment summary">
        {[
          { icon: Users, label: "Candidates with applications", value: stats.candidatesWithApplications },
          { icon: BriefcaseBusiness, label: "Active jobs", value: stats.activeJobs },
          { icon: ClipboardList, label: "Applications", value: stats.applications },
          { icon: UserRoundCheck, label: "Advanced applications", value: stats.advancedApplications },
        ].map((card, i) => (
          <div key={card.label} className="motion-stagger" style={{ "--i": i }}>
            <StatCard icon={card.icon} label={card.label} value={card.value} />
          </div>
        ))}
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
              <Link className="btn btn-secondary" to="/evaluations">Open evaluations</Link>
            </div>
          </div>
        </section>
      )}

      <section className="dashboard-section" aria-labelledby="pipeline-title">
        <div className="dashboard-section-heading">
          <div>
            <h2 id="pipeline-title">Hiring activity</h2>
            <p>Applications by role.</p>
          </div>
          <span className="dashboard-section-note">{stats.applications} applications</span>
        </div>

        {hasApplications ? (
          <div className="charts-grid dashboard-charts dashboard-charts-overview">
            <section className="panel chart-panel dashboard-chart-panel" aria-labelledby="jobs-chart-title">
              <div className="dashboard-chart-heading">
                <div>
                  <h3 id="jobs-chart-title">Applications by job</h3>
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
                  style={{ "--dashboard-chart-height": `${Math.min(Math.max(applicationsByJob.length * 38 + 64, 208), 340)}px` }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={applicationsByJob}
                      layout="vertical"
                      margin={{ top: 8, right: 18, left: 8, bottom: 8 }}
                      barCategoryGap="34%"
                    >
                      <CartesianGrid stroke="var(--color-border)" horizontal={false} />
                      <XAxis
                        type="number"
                        allowDecimals={false}
                        tick={{ fill: "var(--color-muted)", fontSize: 13 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="job"
                        width={170}
                        tick={{ fill: "var(--color-text)", fontSize: 13 }}
                        tickFormatter={formatJobTick}
                        axisLine={false}
                        tickLine={false}
                        interval={0}
                      />
                      <Tooltip
                        cursor={{ fill: "var(--dashboard-chart-cursor)" }}
                        contentStyle={{ border: "1px solid var(--color-border)", borderRadius: 10, background: "var(--color-surface)", color: "var(--color-text)", boxShadow: "0 8px 24px rgba(16, 38, 35, .12)" }}
                      />
                      <Bar dataKey="applications" name="Applications" fill="var(--dashboard-chart-bar)" radius={[0, 5, 5, 0]} maxBarSize={28} />
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
            <aside className="panel dashboard-hiring-insight" aria-labelledby="hiring-insight-title">
              <div className="hiring-insight-kicker"><span><Sparkles size={15} aria-hidden="true" /></span>HERA hiring insight</div>
              {topApplicationJob ? (
                <>
                  <p className="hiring-insight-label">Most applied role</p>
                  <h3 id="hiring-insight-title">{topApplicationJob.job}</h3>
                  <div className="hiring-insight-metrics">
                    <strong>{topApplicationJob.applications}<span> applications</span></strong>
                    <span>{topJobShare}% of total</span>
                  </div>
                  <div className="hiring-insight-track" role="img" aria-label={`${topJobShare}% of applications are for ${topApplicationJob.job}`}>
                    <span style={{ width: `${topJobShare}%` }} />
                  </div>
                  <div className="hiring-insight-footer">
                    <Link to="/applications" aria-label="Review applications">
                      Review applications <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  </div>
                </>
              ) : (
                <div className="hiring-insight-unavailable">
                  <h3 id="hiring-insight-title">Application breakdown unavailable</h3>
                  <p>Role level data will appear here when it is available.</p>
                </div>
              )}
            </aside>
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
