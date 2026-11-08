const fallbackWorkspaceUrl = "http://localhost/BIC2_Mvp/workspace.php";

export const HR_MANAGER_WORKSPACE_URL =
  import.meta.env.VITE_HR_MANAGER_URL || fallbackWorkspaceUrl;

export const HR_MANAGER_LOGOUT_URL =
  import.meta.env.VITE_HR_MANAGER_LOGOUT_URL ||
  new URL("logout.php", HR_MANAGER_WORKSPACE_URL).toString();
