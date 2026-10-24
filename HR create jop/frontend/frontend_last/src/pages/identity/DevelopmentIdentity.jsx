import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Building2, UserPlus, RefreshCw, KeyRound } from "lucide-react";
import useIdentity from "../../hooks/useIdentity";
import * as identityService from "../../services/identityService";

export default function DevelopmentIdentity() {
  const { identity, save, reset } = useIdentity();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    organizationId: identity.organizationId,
    userId: identity.userId,
    organizationName: identity.organizationName,
    userName: identity.userName,
  });

  const [bootstrap, setBootstrap] = useState({
    orgName: "",
    email: "",
    fullName: "",
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const onChange = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }));
  const onBootstrapChange = (name) => (e) =>
    setBootstrap((b) => ({ ...b, [name]: e.target.value }));

  const onSave = (e) => {
    e.preventDefault();
    setError("");
    if (!form.organizationId.trim() || !form.userId.trim()) {
      setError("Organization ID and User ID are required.");
      return;
    }
    save(form);
    navigate("/dashboard", { replace: true });
  };

  const onReset = () => {
    setError("");
    setNotice("");
    const next = reset();
    setForm({
      organizationId: next.organizationId,
      userId: next.userId,
      organizationName: next.organizationName,
      userName: next.userName,
    });
  };

  const onCreateOrganization = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!bootstrap.orgName.trim()) throw new Error("Organization name is required.");
      const org = await identityService.createOrganization(bootstrap.orgName.trim());
      setForm((f) => ({ ...f, organizationId: org.id, organizationName: org.name }));
      setNotice("Organization created. Now create a user within it, or enter a User ID manually.");
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to create organization.");
    } finally {
      setBusy(false);
    }
  };

  const onCreateUser = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const orgId = form.organizationId.trim();
      if (!orgId) throw new Error("Create an organization or enter its ID first.");
      if (!bootstrap.email.trim() || !bootstrap.fullName.trim()) {
        throw new Error("Email and full name are required.");
      }
      const user = await identityService.createUser(orgId, {
        email: bootstrap.email.trim(),
        fullName: bootstrap.fullName.trim(),
      });
      const next = save({ organizationId: user.organization_id, userId: user.id, userName: user.full_name });
      setForm({
        organizationId: next.organizationId,
        userId: next.userId,
        organizationName: next.organizationName,
        userName: next.userName,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to create user.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-card identity-card">
      <div className="identity-header">
        <div className="identity-icon">
          <ShieldCheck size={20} />
        </div>
        <div>
          <h1>Development Identity</h1>
          <p className="auth-subtitle">
            Configures the backend&apos;s development-only header identity. This is{" "}
            <strong>NOT production authentication</strong> — it is a local development helper.
          </p>
        </div>
      </div>

      <div className="dev-note">
        <strong>How it works</strong>
        <span>
          The backend identifies you with <code>X-Organization-Id</code> and{" "}
          <code>X-User-Id</code> headers. No passwords, tokens, or sessions are used.
        </span>
      </div>

      {(error || notice) && (
        <div className={error ? "form-error" : "success-message"}>{error || notice}</div>
      )}

      <form onSubmit={onSave} className="auth-form">
        <label>
          Organization ID
          <div className="input-with-icon">
            <Building2 size={17} />
            <input
              name="organizationId"
              placeholder="00000000-0000-0000-0000-000000000000"
              value={form.organizationId}
              onChange={onChange("organizationId")}
              autoComplete="off"
            />
          </div>
        </label>

        <label>
          User ID
          <div className="input-with-icon">
            <KeyRound size={17} />
            <input
              name="userId"
              placeholder="00000000-0000-0000-0000-000000000000"
              value={form.userId}
              onChange={onChange("userId")}
              autoComplete="off"
            />
          </div>
        </label>

        <div className="auth-row">
          <button className="text-btn" type="button" onClick={onReset}>
            <RefreshCw size={14} /> Reset to defaults
          </button>
        </div>

        <button className="btn btn-primary wide" type="submit" disabled={busy}>
          {busy ? "Saving..." : "Save Identity"}
        </button>
      </form>

      <form onSubmit={onCreateOrganization} className="bootstrap-form">
        <h2>Bootstrap a development identity</h2>
        <p className="auth-subtitle">
          Create an organization and user directly through the backend so you can get a valid ID.
        </p>

        <label>
          Organization name
          <input
            name="orgName"
            placeholder="Acme Inc."
            value={bootstrap.orgName}
            onChange={onBootstrapChange("orgName")}
            autoComplete="off"
          />
        </label>
        <button className="btn btn-secondary wide" type="submit" disabled={busy}>
          <Building2 size={16} /> Create Organization
        </button>

        <div className="divider">then</div>

        <label>
          Email
          <input
            type="email"
            name="email"
            placeholder="you@company.com"
            value={bootstrap.email}
            onChange={onBootstrapChange("email")}
            autoComplete="off"
          />
        </label>
        <label>
          Full name
          <input
            name="fullName"
            placeholder="Sara Ahmed"
            value={bootstrap.fullName}
            onChange={onBootstrapChange("fullName")}
            autoComplete="off"
          />
        </label>
        <button className="btn btn-secondary wide" type="button" onClick={onCreateUser} disabled={busy}>
          <UserPlus size={16} /> Create user & enable identity
        </button>
      </form>

      <p className="auth-footer">
        Current identity:{" "}
        <strong>
          {identity.userId ? `User ${identity.userId.slice(0, 8)} · Org ${identity.organizationId.slice(0, 8)}` : "none"}
        </strong>
      </p>
    </div>
  );
}