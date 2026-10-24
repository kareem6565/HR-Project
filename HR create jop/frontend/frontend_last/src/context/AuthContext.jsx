import React, { createContext, useState, useEffect, useCallback } from "react";
import * as authService from "../services/authService";
import { getToken, clearToken, hasToken } from "../services/authStorage";
import { setUnauthorizedHandler } from "../services/apiClient";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [status, setStatus] = useState("initializing"); // "initializing" | "authenticated" | "unauthenticated" | "unavailable"
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  const checkAuth = useCallback(async () => {
    if (!hasToken()) {
      setUser(null);
      setStatus("unauthenticated");
      setError(null);
      return;
    }

    try {
      const profile = await authService.getCurrentUser();
      setUser(profile);
      setStatus("authenticated");
      setError(null);
    } catch (err) {
      const statusCode = err?.response?.status;
      if (statusCode === 401) {
        clearToken();
        setUser(null);
        setStatus("unauthenticated");
        setError(null);
      } else {
        // Network or server unavailability
        setStatus("unavailable");
        setError(
          "Authentication service is temporarily unavailable. Please check your connection."
        );
      }
    }
  }, []);

  useEffect(() => {
    // Interceptor 401 callback for automatic session invalidation
    setUnauthorizedHandler(() => {
      setUser(null);
      setStatus("unauthenticated");
    });

    checkAuth();
  }, [checkAuth]);

  const login = useCallback(
    async ({ email, password, organizationId }) => {
      setError(null);
      const data = await authService.login({ email, password, organizationId });
      let profile = data?.user;
      if (!profile || !profile.role) {
        profile = await authService.getCurrentUser();
      }
      setUser(profile);
      setStatus("authenticated");
      return profile;
    },
    []
  );

  const loginWithHRAssertion = useCallback(async (assertion) => {
    setError(null);
    const data = await authService.exchangeHRSsoAssertion(assertion);
    const profile = data?.user || (await authService.getCurrentUser());
    setUser(profile);
    setStatus("authenticated");
    return profile;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Regardless of backend response, local session is cleared
    } finally {
      clearToken();
      setUser(null);
      setStatus("unauthenticated");
      setError(null);
    }
  }, []);

  const value = {
    status,
    user,
    error,
    token: getToken(),
    isAuthenticated: status === "authenticated",
    isAdmin: user?.role === "admin" || user?.role === "administrator",
    isRecruiter: user?.role === "recruiter",
    role: user?.role || null,
    login,
    loginWithHRAssertion,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
