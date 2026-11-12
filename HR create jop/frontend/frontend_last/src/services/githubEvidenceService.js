import apiClient from "./apiClient";

export async function requestGitHubEvidenceConsent(applicationId, repositoryUrls = []) {
  const { data } = await apiClient.post(
    `/applications/${applicationId}/github-evidence/consent-link`,
    { repository_urls: repositoryUrls },
  );
  return data;
}

export async function getLatestGitHubEvidence(applicationId) {
  const { data } = await apiClient.get(
    `/applications/${applicationId}/github-evidence/latest`,
  );
  return data;
}

export async function retryGitHubEvidence(applicationId, analysisId) {
  const { data } = await apiClient.post(
    `/applications/${applicationId}/github-evidence/${analysisId}/retry`,
  );
  return data;
}

export async function previewGitHubEvidenceConsent(token) {
  const { data } = await apiClient.post("/candidate-portal/github-evidence-consent/preview", { token });
  return data;
}

export async function respondToGitHubEvidenceConsent(token, decision) {
  const { data } = await apiClient.post("/candidate-portal/github-evidence-consent/respond", {
    token,
    decision,
    self_attested: true,
  });
  return data;
}
