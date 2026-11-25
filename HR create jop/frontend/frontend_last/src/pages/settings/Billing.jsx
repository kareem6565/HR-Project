import React, { useEffect, useState } from "react";
import { RefreshCw, CheckCircle2, Sparkles } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import useAuth from "../../hooks/useAuth";
import {
  getPlans,
  getSubscription,
  getUsage,
  changePlan,
} from "../../services/billingService";

const METER_LABELS = {
  active_jobs: "Active jobs",
  screenings_per_month: "Screenings this month",
  seats: "Team seats",
};

const FEATURE_LABELS = {
  talent_pool: "Talent pool",
  interview_scheduling: "Interview scheduling",
  ocr_cv_intake: "OCR CV intake",
  priority_support: "Priority support",
  audit_exports: "Audit exports",
};

function formatPrice(plan) {
  if (plan.price_monthly_cents === 0) return "Free";
  return `$${(plan.price_monthly_cents / 100).toFixed(0)}/mo`;
}

function formatLimit(value) {
  return value < 0 ? "Unlimited" : value.toLocaleString();
}

export default function Billing() {
  const { isAdmin } = useAuth();
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [formError, setFormError] = useState("");

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([getPlans(), getSubscription(), getUsage()])
      .then(([planRows, sub, usageRow]) => {
        setPlans(planRows);
        setSubscription(sub);
        setUsage(usageRow);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const switchPlan = async (planCode) => {
    setBusy(planCode);
    setNotice("");
    setFormError("");
    try {
      const result = await changePlan(planCode);
      setSubscription(result.subscription);
      setNotice(
        `Plan updated to ${result.subscription.plan.name}. Billing is handled manually for now - our team will reach out about invoicing.`
      );
      const usageRow = await getUsage();
      setUsage(usageRow);
    } catch (err) {
      setFormError(err?.response?.data?.detail || "Plan change failed.");
    } finally {
      setBusy("");
    }
  };

  if (loading) return <LoadingSpinner label="Loading billing..." />;
  if (error || !subscription)
    return <ErrorState message="Unable to load billing details. Try again." onRetry={load} />;

  const currentCode = subscription.plan.code;

  return (
    <section>
      <div className="content-grid settings-grid">
        <div className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">SUBSCRIPTION</p>
              <h3>Billing &amp; Plan</h3>
            </div>
            <button className="btn btn-secondary" onClick={load}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>

          <div className="stats-grid" style={{ marginBottom: "1rem" }}>
            <div className="stat-card">
              <div className="stat-info">
                <span>Current plan</span>
                <strong>{subscription.plan.name}</strong>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-info">
                <span>Status</span>
                <strong style={{ color: "#12B76A" }}>{subscription.status}</strong>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-info">
                <span>Billing mode</span>
                <strong>{subscription.provider === "none" ? "No billing" : "Manual invoicing"}</strong>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-info">
                <span>Renews</span>
                <strong>
                  {subscription.current_period_end
                    ? new Date(subscription.current_period_end).toLocaleDateString()
                    : "—"}
                </strong>
              </div>
            </div>
          </div>

          {usage && (
            <div className="usage-meters">
              {usage.meters.map((meter) => (
                <div key={meter.meter} className="usage-meter">
                  <div className="usage-meter-header">
                    <span>{METER_LABELS[meter.meter] || meter.meter}</span>
                    <strong>
                      {meter.used.toLocaleString()}
                      {meter.unlimited ? " / Unlimited" : ` / ${meter.limit.toLocaleString()}`}
                    </strong>
                  </div>
                  <div className="usage-meter-track">
                    <div
                      className="usage-meter-fill"
                      style={{
                        width: meter.unlimited
                          ? "8%"
                          : `${Math.min(100, meter.percent_used ?? 0)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="dev-note">
            <strong>Manual billing mode</strong>
            <span>
              Paid plans activate instantly and are invoiced by our team while the payment
              integration is being finalized. No card is charged in the product today.
            </span>
          </div>

          {notice && (
            <p className="success-message" role="status">
              <CheckCircle2 size={16} /> {notice}
            </p>
          )}
          {formError && (
            <p className="form-error" role="alert">
              {formError}
            </p>
          )}
        </div>

        <div className="billing-plans">
          {plans.map((plan) => {
            const isCurrent = plan.code === currentCode;
            return (
              <div
                key={plan.code}
                className={`panel billing-plan-card${isCurrent ? " billing-plan-current" : ""}`}
              >
                {plan.code === "pro" && (
                  <span className="badge badge-teal billing-plan-flag">
                    <Sparkles size={12} /> Most popular
                  </span>
                )}
                <p className="eyebrow">{plan.code.toUpperCase()}</p>
                <h3>{plan.name}</h3>
                <p className="billing-plan-price">{formatPrice(plan)}</p>
                <p className="billing-plan-desc">{plan.description}</p>
                <ul className="billing-plan-features">
                  <li>
                    {formatLimit(plan.limits.active_jobs)} active jobs
                  </li>
                  <li>
                    {formatLimit(plan.limits.screenings_per_month)} screenings / month
                  </li>
                  <li>{formatLimit(plan.limits.seats)} seats</li>
                  {Object.entries(plan.features)
                    .filter(([, enabled]) => enabled)
                    .map(([key]) => (
                      <li key={key}>{FEATURE_LABELS[key] || key}</li>
                    ))}
                </ul>
                {isCurrent ? (
                  <button className="btn btn-secondary" disabled>
                    Current plan
                  </button>
                ) : isAdmin ? (
                  <button
                    className="btn btn-primary"
                    disabled={busy !== ""}
                    onClick={() => switchPlan(plan.code)}
                  >
                    {busy === plan.code
                      ? "Switching..."
                      : plan.price_monthly_cents > subscription.plan.price_monthly_cents
                        ? "Upgrade"
                        : "Downgrade"}
                  </button>
                ) : (
                  <button className="btn btn-secondary" disabled title="Only admins can change the plan">
                    Admin only
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
