import React, { useEffect } from "react";
import { HR_MANAGER_LOGIN_URL } from "../../config/hrManager";

const redirectToSharedPortal = (url) => window.location.replace(url);

export default function Login({ redirect = redirectToSharedPortal }) {
  useEffect(() => {
    redirect(HR_MANAGER_LOGIN_URL);
  }, [redirect]);

  return (
    <section className="auth-card panel" aria-labelledby="portal-redirect-title">
      <h1 id="portal-redirect-title">Continue through Smart HR</h1>
      <p className="auth-subtitle">
        HERA sign-in is managed by the shared HR portal. Redirecting you to sign in…
      </p>
      <a className="btn btn-primary wide" href={HR_MANAGER_LOGIN_URL}>
        Open the shared HR portal
      </a>
    </section>
  );
}
