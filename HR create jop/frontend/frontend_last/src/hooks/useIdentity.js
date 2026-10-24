import useAuth from "./useAuth";

/**
 * Compatibility bridge migrating away from legacy development identity.
 * Reads trusted identity directly from the authenticated backend session.
 */
export default function useIdentity() {
  const auth = useAuth();
  return {
    identity: {
      userId: auth.user?.id || "",
      organizationId: auth.user?.organization_id || "",
      userName: auth.user?.full_name || "",
      organizationName: "",
      role: auth.user?.role || "",
    },
    hasIdentity: auth.isAuthenticated,
    save: () => {},
    reset: () => auth.logout(),
  };
}