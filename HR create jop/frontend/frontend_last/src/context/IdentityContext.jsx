import React, { createContext, useState, useCallback } from "react";
import * as identityService from "../services/identityService";

export const IdentityContext = createContext(null);

export function IdentityProvider({ children }) {
  const [identity, setIdentityState] = useState(() => identityService.getIdentity());

  const save = useCallback((patch) => {
    const next = identityService.setIdentity(patch);
    setIdentityState(next);
    return next;
  }, []);

  const reset = useCallback(() => {
    const next = identityService.resetIdentity();
    setIdentityState(next);
    return next;
  }, []);

  const value = {
    identity,
    hasIdentity: Boolean(identity.organizationId && identity.userId),
    save,
    reset,
  };

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}