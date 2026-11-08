import { useEffect } from "react";
import { HR_MANAGER_WORKSPACE_URL } from "../../config/hrManager";

const redirectToHRManager = (url) => window.location.replace(url);

/**
 * HERA recruitment uses the HR Manager sign-in as its only user-facing login.
 * The HR workspace redirects unauthenticated visitors to its PHP login and
 * exchanges authenticated HR sessions through the existing SSO callback.
 */
export default function Login({ redirect = redirectToHRManager }) {
  useEffect(() => {
    redirect(HR_MANAGER_WORKSPACE_URL);
  }, [redirect]);

  return null;
}
