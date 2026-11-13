import { apiRequest } from "./api";

export function loginStaff(email, password) {
  return apiRequest("/auth/staff/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}