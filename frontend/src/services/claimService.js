import { apiBlob, apiRequest } from "./api";

// Each decision has its own URL on the server
const DECISION_PATHS = {
  approve: "approve",
  reject: "reject",
  request_info: "request-info",
  escalate: "escalate",
};

// ---------------------------------------------------------------------------
// Customer
// ---------------------------------------------------------------------------

export function getClaimConfig() {
  return apiRequest("/customer/claim-config");
}

export function listPolicies() {
  return apiRequest("/customer/policies");
}

export function listClaims() {
  return apiRequest("/customer/claims");
}

export function getClaim(claimId) {
  return apiRequest(`/customer/claims/${claimId}`);
}

export function createDraft(policyId) {
  return apiRequest("/customer/claims", {
    method: "POST",
    body: JSON.stringify({ policy_id: policyId }),
  });
}

export function saveDraft(claimId, payload) {
  return apiRequest(`/customer/claims/${claimId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function submitClaim(claimId) {
  return apiRequest(`/customer/claims/${claimId}/submit`, {
    method: "POST",
  });
}

export function respondToInfoRequest(claimId) {
  return apiRequest(`/customer/claims/${claimId}/respond`, {
    method: "POST",
  });
}

export function listHistory(claimId) {
  return apiRequest(`/customer/claims/${claimId}/history`);
}

export function listDocuments(claimId) {
  return apiRequest(`/customer/claims/${claimId}/documents`);
}

export function uploadDocument(claimId, docType, file) {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("file", file);

  return apiRequest(`/customer/claims/${claimId}/documents`, {
    method: "POST",
    body: formData,
  });
}

export function downloadDocument(claimId, documentId) {
  return apiBlob(`/customer/claims/${claimId}/documents/${documentId}/file`);
}

export function listMessages(claimId) {
  return apiRequest(`/customer/claims/${claimId}/messages`);
}

export function postMessage(claimId, body) {
  return apiRequest(`/customer/claims/${claimId}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

// ---------------------------------------------------------------------------
// Staff
// ---------------------------------------------------------------------------

export function getStaffDashboard() {
  return apiRequest("/staff/dashboard");
}

export function listStaffClaims(view, line, search) {
  const params = new URLSearchParams();
  params.set("view", view);

  if (line) {
    params.set("line", line);
  }

  if (search) {
    params.set("search", search);
  }

  return apiRequest(`/staff/claims?${params.toString()}`);
}

export function getStaffClaim(claimId) {
  return apiRequest(`/staff/claims/${claimId}`);
}

export function downloadStaffDocument(claimId, documentId) {
  return apiBlob(`/staff/claims/${claimId}/documents/${documentId}/file`);
}

export function assignClaimToMe(claimId) {
  return apiRequest(`/staff/claims/${claimId}/assign`, {
    method: "POST",
  });
}

export function addStaffNote(claimId, note) {
  return apiRequest(`/staff/claims/${claimId}/notes`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export function recordDecision(claimId, decision, reason, customerMessage) {
  const path = DECISION_PATHS[decision];

  return apiRequest(`/decisions/claims/${claimId}/${path}`, {
    method: "POST",
    body: JSON.stringify({
      reason,
      customer_message: customerMessage,
    }),
  });
}

export function getStaffDocumentOcr(claimId, documentId) {
  return apiRequest(`/staff/claims/${claimId}/documents/${documentId}/ocr`);
}