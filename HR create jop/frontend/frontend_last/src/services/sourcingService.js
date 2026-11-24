// LinkedIn candidate sourcing service.
//
// INTEGRATION POINT (backend pending): the team will add the sourcing API
// (expected shape: POST /sourcing/linkedin/searches -> { id, status },
// GET /sourcing/linkedin/searches/:id -> { status, candidates[] }).
// Until then searchLinkedInCandidates resolves with { status: "unavailable" }
// so the UI lands on its honest empty state instead of an error.
// Everything in pages/sourcing/ depends only on this module - swap the stub
// for real apiClient calls here and the UI needs no changes.

export async function searchLinkedInCandidates(/* criteria */) {
  // Stub: no backend route exists yet.
  return { status: "unavailable", candidates: [] };
}
