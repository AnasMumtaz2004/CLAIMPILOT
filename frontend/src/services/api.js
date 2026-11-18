const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "claimpilot_token";

function getErrorMessage(data, status) {
  if (data && typeof data.detail === "string") {
    return data.detail;
  }

  if (data && Array.isArray(data.detail)) {
    const messages = [];
    data.detail.forEach((item) => {
      messages.push(item.msg);
    });
    return messages.join(", ");
  }

  return `Request failed (${status}).`;
}

function buildHeaders(extraHeaders) {
  const headers = { ...(extraHeaders || {}) };
  const token = localStorage.getItem(TOKEN_KEY);

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

async function sendRequest(path, options, headers) {
  try {
    return await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }
}

export async function apiRequest(path, options = {}) {
  const headers = buildHeaders(options.headers);

  const isFormData = options.body instanceof FormData;
  if (options.body && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const response = await sendRequest(path, options, headers);

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(getErrorMessage(data, response.status));
    error.status = response.status;
    throw error;
  }

  return data;
}

export async function apiBlob(path) {
  const headers = buildHeaders();
  const response = await sendRequest(path, {}, headers);

  if (!response.ok) {
    const error = new Error("Could not load the file.");
    error.status = response.status;
    throw error;
  }

  return response.blob();
}