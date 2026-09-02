import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";

// Standardized frontend API error
export type ApiError = {
  status: number;
  message: string;
  errors?: Record<string, unknown>;
};

// Create the centralized Axios instance
export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true, // Crucial for sending Django session cookies
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
  headers: {
    "Content-Type": "application/json",
  },
});

// Helper to extract a cookie value by name
function getCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookies = document.cookie.split("; ");
  for (const cookie of cookies) {
    const [key, ...valueParts] = cookie.split("=");
    if (key.trim() === name) {
      return decodeURIComponent(valueParts.join("="));
    }
  }

  return null;
}

// Request Interceptor: Attach CSRF Token for unsafe methods
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const method = config.method?.toUpperCase();
    if (method && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const csrfToken = getCookie("csrftoken");
      if (csrfToken) {
        if (config.headers && typeof config.headers.set === "function") {
          config.headers.set("X-CSRFToken", csrfToken);
        } else if (config.headers) {
          (config.headers as Record<string, string>)["X-CSRFToken"] = csrfToken;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Normalize errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    const apiError: ApiError = {
      status: error.response?.status || 500,
      message: "An unexpected error occurred",
    };

    if (error.response?.data) {
      const data = error.response.data as Record<string, unknown>;
      // Extract errors object from Keel custom exception format or fallback to entire data
      if (data.errors && typeof data.errors === "object") {
        apiError.errors = data.errors as Record<string, unknown>;
      } else {
        apiError.errors = data;
      }

      // Normalize Django/DRF error structure
      if (typeof data.detail === "string") {
        apiError.message = data.detail;
      } else if (typeof data.message === "string") {
        apiError.message = data.message;
      } else if (Array.isArray(data.non_field_errors)) {
        apiError.message = data.non_field_errors[0];
      } else if (!data.errors) {
        apiError.message = "Validation Error";
      }
    } else if (error.message) {
      apiError.message = error.message;
    }

    // Specific status code handling (e.g., redirect to login on 401 if needed)
    if (apiError.status === 401) {
      // We can emit an event or let the QueryClient/Auth hook handle it
      console.warn("Unauthenticated request (401)");
    } else if (apiError.status === 403) {
      console.warn("Permission denied (403)");
    }

    return Promise.reject(apiError);
  }
);
