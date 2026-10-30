import React, { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import BrandIcon from "../../components/common/BrandIcon";

export default function SsoCallback() {
  const { loginWithHRAssertion } = useAuth();
  const [state, setState] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const hrManagerUrl = import.meta.env.VITE_HR_MANAGER_URL;

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const assertion = params.get("assertion");
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!assertion) {
      setState("error");
      setErrorMessage("The HR sign-in link is missing. Return to the HR workspace and try again.");
      return;
    }

    let active = true;
    loginWithHRAssertion(assertion)
      .then(() => active && setState("done"))
      .catch((error) => {
        if (!active) return;
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail;
        if (status === 401) {
          setErrorMessage("The HR sign-in link has expired or is invalid. Return to the HR workspace and try again.");
        } else if (status === 403) {
          setErrorMessage("This HR account is not active for Recruitment access. Ask your HR administrator to review your account.");
        } else if (status === 503 && /organization/i.test(detail || "")) {
          setErrorMessage("Your account could not be linked to the HERA organization. Ask your administrator to verify the organization setup.");
        } else if (status === 503) {
          setErrorMessage("HERA single sign-on is not fully configured. Ask your administrator to check the HR integration settings.");
        } else {
          setErrorMessage("HERA could not complete account setup. Return to the HR workspace and try again.");
        }
        setState("error");
      });
    return () => {
      active = false;
    };
  }, [loginWithHRAssertion]);

  if (state === "done") return <Navigate to="/dashboard" replace />;

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
          <>
            <h1>Sign-in could not be completed</h1>
            <p className="auth-subtitle" role="alert">{errorMessage}</p>
            {hrManagerUrl ? (
              <a className="btn btn-primary" href={hrManagerUrl}>Return to HR workspace</a>
            ) : (
              <Link className="btn btn-primary" to="/login">Go to HERA login</Link>
            )}
          </>
        )}
      </section>
    </main>
  );
}
