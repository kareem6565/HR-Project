import React, { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import BrandIcon from "../../components/common/BrandIcon";

export default function SsoCallback() {
  const { isAuthenticated, loginWithHRAssertion } = useAuth();
  const [state, setState] = useState("loading");

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const assertion = params.get("assertion");
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!assertion) {
      setState("error");
      return;
    }

    let active = true;
    loginWithHRAssertion(assertion)
      .then(() => active && setState("done"))
      .catch(() => active && setState("error"));
    return () => {
      active = false;
    };
  }, [loginWithHRAssertion]);

  if (state === "done" || isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <main className="auth-shell" aria-live="polite">
      <section className="auth-card panel" style={{ maxWidth: 480, margin: "12vh auto", padding: 32 }}>
        <div className="brand" style={{ marginBottom: 24 }}>
          <div className="brand-icon"><BrandIcon size={20} /></div>
          <div><strong>HERA</strong><span>Recruitment</span></div>
        </div>
        {state === "loading" ? (
          <><h1>Signing you in</h1><p className="auth-subtitle">Verifying your HR account with HERA.</p></>
        ) : (
          <><h1>Sign-in could not be completed</h1><p className="auth-subtitle">The link may have expired or the HERA SSO settings need attention. Return to the HR workspace and try again.</p><Link className="btn btn-primary" to="/login">Go to HERA login</Link></>
        )}
      </section>
    </main>
  );
}
