import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  // Send the mnx_session cookie set by /auth/login even when the web-ui and
  // core-api are on different origins (production, non-proxied deployments).
  withCredentials: true,
});
