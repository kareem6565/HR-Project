import React, { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import HeraAssistantMark from "../../components/common/HeraAssistantMark";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import { getAnalyticsSnapshot, getCandidateSources } from "../../services/analyticsService";

const DATE_RANGES = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
];

export default function AnalyticsPage() {
  const [range, setRange] = useState("30d");
  const [retryCount, setRetryCount] = useState(0);
  const [snapshot, setSnapshot] = useState(null);
  const [sources, setSources] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    Promise.all([getAnalyticsSnapshot(range), getCandidateSources()])
      .then(([nextSnapshot, nextSources]) => {
        if (!active) return;
        setSnapshot(nextSnapshot);
        setSources(nextSources);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError(true);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [range, retryCount]);

  if (loading) return <LoadingSpinner label="Loading analytics..." />;
  if (error) {
    return <ErrorState message="Unable to load analytics. Please try again." onRetry={() => setRetryCount((count) => count + 1)} />;
  }

  const totalApplications = snapshot.statusBreakdown.reduce((sum, row) => sum + row.count, 0);
  const periodLabel = range === "30d" ? "last 30 days" : "last 90 days";

  return (
    <section className="analytics-page" aria-labelledby="analytics-title">
      <header className="analytics-heading">
        <div className="analytics-heading-copy">
          <p className="analytics-kicker">
            <HeraAssistantMark size={25} />
            <span>HERA · AI-ASSISTED, HR-LED</span>
          </p>
          <h2 id="analytics-title">Hiring patterns and outcomes</h2>
          <p>Explore application volume and current status within a selected creation period.</p>
        </div>
        <fieldset className="analytics-range">
          <legend><CalendarDays size={14} aria-hidden="true" /> Application creation period</legend>
          <div className="analytics-range-options">
            {DATE_RANGES.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={range === option.value}
                onClick={() => setRange(option.value)}
              >
                Last {option.label}
              </button>
            ))}
          </div>
        </fieldset>
      </header>

      <p className="analytics-scope-note">
        Metrics include applications created in the {periodLabel}. Status and score describe their current recorded values.
      </p>

      <section className="stats-grid analytics-stats" aria-label={`Hiring metrics for the ${periodLabel}`}>
        {snapshot.metrics.map((metric) => (
          <article className="stat-card metric-card analytics-stat-card" key={metric.key}>
            <div className="stat-info">
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <div className="metric-delta">{metric.deltaLabel}</div>
            </div>
          </article>
        ))}
      </section>

      <div className="analytics-analysis-grid">
        <section className="panel analytics-panel" aria-labelledby="trend-title">
          <div className="analytics-panel-heading">
            <div>
              <h3 id="trend-title">Applications created by week</h3>
              <p>New applications grouped into seven-day intervals during the selected period.</p>
            </div>
            <span className="analytics-range-badge">{range === "30d" ? "30 days" : "90 days"}</span>
          </div>
          {totalApplications > 0 ? (
            <div className="analytics-trend-chart" role="img" aria-label={`Line chart of applications created by week in the ${periodLabel}`}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={snapshot.applicationTrend} margin={{ top: 12, right: 12, left: -16, bottom: 2 }}>
                  <CartesianGrid stroke="var(--hera-border)" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "var(--hera-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} width={36} tick={{ fill: "var(--hera-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="applications" name="Applications created" stroke="var(--hera-teal)" strokeWidth={3} dot={{ r: 3, fill: "var(--hera-gold)" }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="analytics-empty">No application records were created in the {periodLabel}.</p>
          )}
        </section>

        <section className="panel analytics-panel" aria-labelledby="status-title">
          <div className="analytics-panel-heading">
            <div>
              <h3 id="status-title">Current application status</h3>
              <p>Each application is counted once by its current status.</p>
            </div>
          </div>
          {totalApplications > 0 ? (
            <div className="funnel-bars">
              {snapshot.statusBreakdown.map((row) => (
                <div className="funnel-row" key={row.stage}>
                  <span className="funnel-label">{row.stage}</span>
                  <div className="funnel-track" aria-hidden="true">
                    <div className="funnel-fill" style={{ width: `${row.percent}%` }} />
                  </div>
                  <span className="funnel-percent">{row.count} · {row.percent}%</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="analytics-empty">Status counts will appear when applications are created in this period.</p>
          )}
          <p className="analytics-denominator-note">
            Percentages are shares of the {totalApplications} in-period applications, not stage-to-stage conversion rates.
          </p>
        </section>

        <section className="panel analytics-sources" aria-labelledby="sources-title">
          <div className="analytics-panel-heading">
            <div>
              <h3 id="sources-title">Candidate sources</h3>
              <p>Source attribution is separate from application status.</p>
            </div>
            <span className={`analytics-unavailable-badge${sources === null ? "" : " is-available"}`}>
              {sources === null ? "Not collected" : "Available"}
            </span>
          </div>
          {sources === null ? (
            <p className="analytics-source-note">HERA does not currently collect candidate-source data, so no source totals can be reported.</p>
          ) : sources.length === 0 ? (
            <p className="analytics-source-note">No candidate-source records are available for this workspace.</p>
          ) : (
            <p className="analytics-source-note">Candidate-source data is available.</p>
          )}
        </section>
      </div>
    </section>
  );
}
