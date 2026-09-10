import type {
  AdminUser,
  AttendanceRow,
  AuditEntry,
  Device,
  DeviceCommand,
  DeviceEvent,
  DeviceUser,
  Me,
} from "@/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Typed API error carrying HTTP status + backend error code (§66 envelope). */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface Tokens {
  access: string;
  refresh: string;
}

/**
 * Token storage: IN-MEMORY ONLY (module singleton). No localStorage/
 * sessionStorage, so a stored-XSS cannot exfiltrate a persistent session
 * (see docs/SECURITY.md). Trade-off: reloads require re-login; the refresh
 * token lives as long as the tab. A future httpOnly-cookie transport is
 * documented as the follow-up.
 */
class ApiClient {
  private tokens: Tokens | null = null;
  private refreshFlight: Promise<boolean> | null = null;

  get authenticated(): boolean {
    return this.tokens !== null;
  }

  setTokens(access: string, refresh: string): void {
    this.tokens = { access, refresh };
  }

  clearTokens(): void {
    this.tokens = null;
  }

  private async raw(path: string, token: string | null, init?: RequestInit): Promise<Response> {
    return fetch(`${API}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  }

  private async parseError(res: Response): Promise<never> {
    let code = "HTTP_ERROR";
    let message = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string } };
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      /* non-JSON error body */
    }
    const retryAfter = res.headers.get("Retry-After");
    throw new ApiError(res.status, code, message, retryAfter ? Number(retryAfter) : undefined);
  }

  /** Single-flight refresh shared by concurrent 401s (loop-guard: one retry max). */
  private refreshOnce(): Promise<boolean> {
    if (!this.refreshFlight) {
      this.refreshFlight = (async () => {
        try {
          if (!this.tokens) return false;
          const res = await this.raw(
            "/api/v1/auth/refresh",
            null,
            { method: "POST", body: JSON.stringify({ refresh_token: this.tokens.refresh }) },
          );
          if (!res.ok) {
            this.clearTokens();
            return false;
          }
          const body = (await res.json()) as { access_token: string; refresh_token: string };
          this.tokens = { access: body.access_token, refresh: body.refresh_token };
          return true;
        } finally {
          this.refreshFlight = null;
        }
      })();
    }
    return this.refreshFlight;
  }

  async request<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
    let res = await this.raw(path, this.tokens?.access ?? null, init);
    if (res.status === 401 && retry && this.tokens) {
      const refreshed = await this.refreshOnce();
      if (refreshed) {
        res = await this.raw(path, this.tokens?.access ?? null, init);
      }
    }
    if (!res.ok) await this.parseError(res);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  // -- auth ---------------------------------------------------------------
  async login(username: string, password: string): Promise<Me> {
    const res = await this.raw(
      "/api/v1/auth/login",
      null,
      { method: "POST", body: JSON.stringify({ username, password }) },
    );
    if (!res.ok) await this.parseError(res);
    const body = (await res.json()) as { access_token: string; refresh_token: string };
    this.setTokens(body.access_token, body.refresh_token);
    return this.me();
  }

  async logout(): Promise<void> {
    try {
      if (this.tokens) {
        await this.raw(
          "/api/v1/auth/logout",
          this.tokens.access,
          { method: "POST", body: JSON.stringify({ refresh_token: this.tokens.refresh }) },
        );
      }
    } finally {
      this.clearTokens();
    }
  }

  me(): Promise<Me> {
    return this.request<Me>("/api/v1/auth/me");
  }

  // -- resources ----------------------------------------------------------
  summary(): Promise<Record<string, number>> {
    return this.request("/api/v1/devices/stats/summary");
  }

  devices(params: Record<string, string> = {}): Promise<Device[]> {
    return this.get("/api/v1/devices", params);
  }

  device(id: string): Promise<Device> {
    return this.request(`/api/v1/devices/${id}`);
  }

  patchDevice(id: string, body: Record<string, unknown>): Promise<Device> {
    return this.request(`/api/v1/devices/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  }

  deviceEvents(id: string): Promise<DeviceEvent[]> {
    return this.request(`/api/v1/devices/${id}/events?limit=50`);
  }

  attendance(params: Record<string, string> = {}): Promise<AttendanceRow[]> {
    return this.get("/api/v1/attendance", params);
  }

  deviceUsers(deviceId?: string): Promise<DeviceUser[]> {
    return this.request(
      `/api/v1/device-users${deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : ""}`,
    );
  }

  createDeviceUser(deviceId: string, body: Record<string, unknown>): Promise<DeviceUser> {
    return this.request(`/api/v1/device-users/${deviceId}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  updateDeviceUser(id: string, body: Record<string, unknown>): Promise<DeviceUser> {
    return this.request(`/api/v1/device-users/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  deleteDeviceUser(id: string): Promise<DeviceUser> {
    return this.request(`/api/v1/device-users/${id}`, { method: "DELETE" });
  }

  deviceCommands(deviceId: string): Promise<DeviceCommand[]> {
    return this.request(`/api/v1/devices/${deviceId}/commands`);
  }

  queueCommand(deviceId: string, command_type: string, params: Record<string, string> = {}) {
    return this.request<DeviceCommand>(`/api/v1/devices/${deviceId}/commands`, {
      method: "POST",
      body: JSON.stringify({ command_type, params }),
    });
  }

  commands(status?: string): Promise<DeviceCommand[]> {
    return this.request(`/api/v1/commands${status ? `?status=${encodeURIComponent(status)}` : ""}`);
  }

  users(): Promise<AdminUser[]> {
    return this.request("/api/v1/users");
  }

  createUser(body: Record<string, unknown>): Promise<AdminUser> {
    return this.request("/api/v1/users", { method: "POST", body: JSON.stringify(body) });
  }

  updateUser(id: string, body: Record<string, unknown>): Promise<AdminUser> {
    return this.request(`/api/v1/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  }

  deleteUser(id: string): Promise<void> {
    return this.request(`/api/v1/users/${id}`, { method: "DELETE" });
  }

  audit(): Promise<AuditEntry[]> {
    return this.request("/api/v1/audit?limit=100");
  }

  private get<T>(path: string, params: Record<string, string>): Promise<T> {
    const q = new URLSearchParams(params).toString();
    return this.request<T>(`${path}${q ? `?${q}` : ""}`);
  }
}

export const api = new ApiClient();
