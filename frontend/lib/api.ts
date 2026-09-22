import type {
  AdminUser,
  AbsenceReport,
  AttendanceAdjustment,
  AttendanceRow,
  AuditEntry,
  Company,
  CorporateGroup,
  Device,
  DeviceCapabilityProfile,
  DeviceCommand,
  DeviceEvent,
  DeviceUser,
  DailyArrivalReport,
  Employment,
  EmploymentCompensation,
  EnrollmentRequest,
  Holiday,
  HardDeleteCaptcha,
  Me,
  Person,
  PersonPhoto,
  PersonAttendancePage,
  PersonSensitiveIdentifiers,
  PunctualityReport,
  ScheduleAssignment,
  Site,
  WeeklyCardReport,
  WorkSchedule,
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
    const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
    return fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

  private async download(path: string, retry = true): Promise<Blob> {
    let res = await this.raw(path, this.tokens?.access ?? null);
    if (res.status === 401 && retry && this.tokens && await this.refreshOnce()) {
      res = await this.raw(path, this.tokens?.access ?? null);
    }
    if (!res.ok) await this.parseError(res);
    return res.blob();
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

  createDevice(body: Record<string, unknown>): Promise<Device> {
    return this.request("/api/v1/devices", { method: "POST", body: JSON.stringify(body) });
  }

  device(id: string): Promise<Device> {
    return this.request(`/api/v1/devices/${id}`);
  }

  deviceCapabilities(id: string): Promise<DeviceCapabilityProfile> {
    return this.request(`/api/v1/devices/${id}/capabilities`);
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

  resolveAttendanceAttribution(id: string, employmentId: string, reason: string): Promise<AttendanceRow> {
    return this.request(`/api/v1/attendance/${id}/attribution`, {
      method: "PUT",
      body: JSON.stringify({ employment_id: employmentId, reason }),
    });
  }

  dailyArrivals(params: Record<string, string>): Promise<DailyArrivalReport[]> {
    return this.get("/api/v1/reports/daily-arrivals", params);
  }

  absencesReport(params: Record<string, string>): Promise<AbsenceReport[]> {
    return this.get("/api/v1/reports/absences", params);
  }

  weeklyCard(params: Record<string, string>): Promise<WeeklyCardReport> {
    return this.get("/api/v1/reports/weekly-card", params);
  }

  punctualityReport(params: Record<string, string>): Promise<PunctualityReport[]> {
    return this.get("/api/v1/reports/punctuality", params);
  }

  attendanceAdjustments(params: Record<string, string>): Promise<AttendanceAdjustment[]> {
    return this.get("/api/v1/reports/adjustments", params);
  }

  saveAttendanceAdjustment(employmentId: string, body: Record<string, unknown>): Promise<AttendanceAdjustment> {
    return this.request(`/api/v1/reports/adjustments/${employmentId}`, { method: "PUT", body: JSON.stringify(body) });
  }

  weeklyCardsPdf(params: Record<string, string>): Promise<Blob> {
    return this.download(`/api/v1/reports/weekly-cards.pdf?${new URLSearchParams(params).toString()}`);
  }

  corporateGroups(): Promise<CorporateGroup[]> {
    return this.request("/api/v1/corporate-groups");
  }

  createCorporateGroup(body: Record<string, unknown>): Promise<CorporateGroup> {
    return this.request("/api/v1/corporate-groups", { method: "POST", body: JSON.stringify(body) });
  }

  companies(groupId?: string, includeInactive = false): Promise<Company[]> {
    return this.get("/api/v1/companies", { ...(groupId ? { corporate_group_id: groupId } : {}), ...(includeInactive ? { include_inactive: "true" } : {}) });
  }

  createCompany(body: Record<string, unknown>): Promise<Company> {
    return this.request("/api/v1/companies", { method: "POST", body: JSON.stringify(body) });
  }

  updateCompany(id: string, body: Record<string, unknown>): Promise<Company> {
    return this.request(`/api/v1/companies/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  }

  deleteCompany(id: string): Promise<void> {
    return this.request(`/api/v1/companies/${id}`, { method: "DELETE" });
  }

  companyHardDeleteCaptcha(id: string): Promise<HardDeleteCaptcha> {
    return this.request(`/api/v1/companies/${id}/hard-delete-captcha`, { method: "POST" });
  }

  hardDeleteCompany(id: string, body: Record<string, unknown>): Promise<void> {
    return this.request(`/api/v1/companies/${id}/hard`, { method: "DELETE", body: JSON.stringify(body) });
  }

  sites(companyId?: string, includeInactive = false): Promise<Site[]> {
    return this.get("/api/v1/sites", { ...(companyId ? { company_id: companyId } : {}), ...(includeInactive ? { include_inactive: "true" } : {}) });
  }

  createSite(body: Record<string, unknown>): Promise<Site> {
    return this.request("/api/v1/sites", { method: "POST", body: JSON.stringify(body) });
  }

  updateSite(id: string, body: Record<string, unknown>): Promise<Site> {
    return this.request(`/api/v1/sites/${id}`, { method: "PATCH", body: JSON.stringify(body) });
  }

  deleteSite(id: string): Promise<void> {
    return this.request(`/api/v1/sites/${id}`, { method: "DELETE" });
  }

  siteHardDeleteCaptcha(id: string): Promise<HardDeleteCaptcha> {
    return this.request(`/api/v1/sites/${id}/hard-delete-captcha`, { method: "POST" });
  }

  hardDeleteSite(id: string, body: Record<string, unknown>): Promise<void> {
    return this.request(`/api/v1/sites/${id}/hard`, { method: "DELETE", body: JSON.stringify(body) });
  }

  people(corporateGroupId: string): Promise<Person[]> {
    return this.get("/api/v1/people", { corporate_group_id: corporateGroupId });
  }

  person(personId: string): Promise<Person> {
    return this.request(`/api/v1/people/${personId}`);
  }

  personAttendance(personId: string, params: Record<string, string> = {}): Promise<PersonAttendancePage> {
    return this.get(`/api/v1/people/${personId}/attendance`, params);
  }

  createPerson(body: Record<string, unknown>): Promise<Person> {
    return this.request("/api/v1/people", { method: "POST", body: JSON.stringify(body) });
  }

  updatePerson(personId: string, body: Record<string, unknown>): Promise<Person> {
    return this.request(`/api/v1/people/${personId}`, { method: "PATCH", body: JSON.stringify(body) });
  }

  personSensitive(personId: string): Promise<PersonSensitiveIdentifiers> {
    return this.request(`/api/v1/people/${personId}/sensitive`);
  }

  async personPhoto(personId: string): Promise<Blob | null> {
    let res = await this.raw(`/api/v1/people/${personId}/photo`, this.tokens?.access ?? null);
    if (res.status === 401 && this.tokens && await this.refreshOnce()) {
      res = await this.raw(`/api/v1/people/${personId}/photo`, this.tokens?.access ?? null);
    }
    if (res.status === 404) return null;
    if (!res.ok) await this.parseError(res);
    return res.blob();
  }

  uploadPersonPhoto(personId: string, photo: File): Promise<PersonPhoto> {
    const body = new FormData();
    body.append("photo", photo);
    return this.request(`/api/v1/people/${personId}/photo`, { method: "PUT", body });
  }

  deletePersonPhoto(personId: string): Promise<void> {
    return this.request(`/api/v1/people/${personId}/photo`, { method: "DELETE" });
  }

  updatePersonSensitive(personId: string, body: Record<string, unknown>): Promise<PersonSensitiveIdentifiers> {
    return this.request(`/api/v1/people/${personId}/sensitive`, { method: "PUT", body: JSON.stringify(body) });
  }

  employments(params: Record<string, string> = {}): Promise<Employment[]> {
    return this.get("/api/v1/employments", params);
  }

  createEmployment(personId: string, body: Record<string, unknown>): Promise<Employment> {
    return this.request(`/api/v1/people/${personId}/employments`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  employmentCompensation(employmentId: string): Promise<EmploymentCompensation> {
    return this.request(`/api/v1/employments/${employmentId}/compensation`);
  }

  updateEmploymentCompensation(
    employmentId: string,
    body: Record<string, unknown>,
  ): Promise<EmploymentCompensation> {
    return this.request(`/api/v1/employments/${employmentId}/compensation`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  workSchedules(companyId?: string): Promise<WorkSchedule[]> {
    return this.get("/api/v1/work-schedules", companyId ? { company_id: companyId } : {});
  }

  createWorkSchedule(body: Record<string, unknown>): Promise<WorkSchedule> {
    return this.request("/api/v1/work-schedules", { method: "POST", body: JSON.stringify(body) });
  }

  updateWorkSchedule(id: string, body: Record<string, unknown>): Promise<WorkSchedule> {
    return this.request(`/api/v1/work-schedules/${id}`, { method: "PUT", body: JSON.stringify(body) });
  }

  deleteWorkSchedule(id: string): Promise<void> {
    return this.request(`/api/v1/work-schedules/${id}`, { method: "DELETE" });
  }

  assignWorkSchedule(employmentId: string, body: Record<string, unknown>): Promise<unknown> {
    return this.request(`/api/v1/employments/${employmentId}/schedule-assignments`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  scheduleAssignments(employmentId: string): Promise<ScheduleAssignment[]> {
    return this.request(`/api/v1/employments/${employmentId}/schedule-assignments`);
  }

  holidays(companyId: string, year: number): Promise<Holiday[]> {
    return this.get("/api/v1/holidays", { company_id: companyId, year: String(year) });
  }

  createHoliday(body: Record<string, unknown>): Promise<Holiday> {
    return this.request("/api/v1/holidays", { method: "POST", body: JSON.stringify(body) });
  }

  generateHolidays(companyId: string, year: number): Promise<{ year: number; created: number; existing: number }> {
    return this.request(`/api/v1/companies/${companyId}/holidays/generate?year=${year}`, { method: "POST" });
  }

  enrollmentRequests(): Promise<EnrollmentRequest[]> {
    return this.request("/api/v1/enrollment-requests");
  }

  createEnrollmentRequest(body: Record<string, unknown>): Promise<EnrollmentRequest> {
    return this.request("/api/v1/enrollment-requests", { method: "POST", body: JSON.stringify(body) });
  }

  updateEnrollmentRequest(id: string, body: Record<string, unknown>): Promise<EnrollmentRequest> {
    return this.request(`/api/v1/enrollment-requests/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
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
