import { apiRequest } from "./api";

export function registerCustomer(fullName, email, password) {
  return apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email,
      password,
    }),
  });
}

export function loginCustomer(email, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function fetchCurrentUser() {
  return apiRequest("/auth/me");
}