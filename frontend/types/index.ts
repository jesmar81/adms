export interface Device {
  id: string;
  serial_number: string;
  name: string | null;
  model: string | null;
  firmware_version: string | null;
  platform: string | null;
  ip_address: string | null;
  mac_address: string | null;
  site_id: string | null;
  timezone: string;
  status: string;
  derived_status?: string | null;
  last_activity_at: string | null;
  options: Record<string, string>;
}

export interface DeviceCapabilityProfile {
  profile: "security_push_acc" | "legacy_adms";
  firmware: string | null;
  confirmed: {
    realtime_attendance: boolean;
    realtime_state: boolean;
    command_poll: boolean;
    info_command: boolean;
    user_querydata_received: boolean;
  };
  safe_commands: string[];
  blocked_operations: string[];
  next_validation: string | null;
}

export interface AttendanceRow {
  id: string;
  device_id: string;
  device_user_pin: string;
  recorded_at: string;
  status: number;
  verify_mode: number;
  work_code: string | null;
  attribution_status: "assigned" | "ambiguous" | "unassigned";
  employment_id: string | null;
}

export interface DailyArrivalReport {
  person_id: string;
  employment_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  report_date: string;
  first_mark_at: string;
  mark_count: number;
}

export interface LivePunctualityRow {
  employment_id: string;
  person_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  site_name: string | null;
  scheduled_entry_at: string;
  arrival_at: string | null;
  status: "not_arrived" | "late";
  minutes_after_start: number;
  late_minutes: number;
  tolerance_remaining_minutes: number;
}

export interface LivePunctualityReport {
  company_id: string;
  report_date: string;
  generated_at: string;
  scheduled_count: number;
  arrived_on_time_count: number;
  pending_arrival_count: number;
  pending_beyond_tolerance_count: number;
  late_count: number;
  late_minutes_total: number;
  rows: LivePunctualityRow[];
}

export interface AbsenceReport {
  person_id: string;
  employment_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  report_date: string;
  expected_entry_at: string;
}

export interface WeeklyCardDay {
  report_date: string;
  day_kind: string;
  entry_at: string | null;
  meal_out_at: string | null;
  meal_in_at: string | null;
  exit_at: string | null;
  mark_count: number;
  late_minutes: number;
  early_departure_minutes: number;
  overtime_minutes: number;
  adjustment_id: string | null;
  adjustment_reason: string | null;
}

export interface WeeklyCardReport {
  employment_id: string;
  person_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  site_name: string | null;
  address: string | null;
  week_start: string;
  week_end: string;
  days: WeeklyCardDay[];
}

export interface AttendanceAdjustment {
  id: string;
  employment_id: string;
  attendance_date: string;
  entry_at: string | null;
  meal_out_at: string | null;
  meal_in_at: string | null;
  exit_at: string | null;
  absence_kind: "justified" | "unjustified" | null;
  reason: string;
  created_at: string;
  updated_at: string;
}

export interface PunctualityReport {
  person_id: string;
  employment_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  report_date: string;
  expected_entry_at: string | null;
  first_mark_at: string | null;
  late_minutes: number;
  expected_exit_at: string | null;
  last_mark_at: string | null;
  early_departure_minutes: number;
}

export interface AttendanceDashboard {
  company_id: string;
  report_date: string;
  scheduled_workers: number;
  present_workers: number;
  on_time_workers: number;
  late_workers: number;
  late_minutes: number;
  absent_workers: number;
  justified_absences: number;
  raw_marks: number;
  unresolved_marks: number;
  overtime_pending_hr: number;
  overtime_pending_direction: number;
  overtime_authorized_minutes: number;
}

export interface OvertimeRequest {
  id: string;
  person_id: string;
  employment_id: string;
  worker_name: string;
  employee_number: string;
  company_name: string;
  report_date: string;
  source: "detected" | "manual";
  status: "pending_hr" | "pending_direction" | "approved" | "rejected" | "cancelled";
  scheduled_exit_at: string | null;
  detected_exit_at: string | null;
  minutes: number;
  reviewed_minutes: number | null;
  authorized_minutes: number | null;
  reason: string;
  review_note: string | null;
  authorization_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  authorized_at: string | null;
}

export interface PersonAttendancePage {
  items: AttendanceRow[];
  next_cursor: string | null;
}

export interface DeviceUser {
  id: string;
  device_id: string;
  person_id: string | null;
  pin: string;
  name: string;
  privilege: number;
  card_number: string | null;
  enabled: boolean;
  sync_state: string;
  last_protocol_command_id: number | null;
  last_synced_at: string | null;
}

export interface PersonDeviceUserLink {
  device_id: string;
  device_name: string | null;
  device_serial_number: string;
  pin: string;
  device_name_on_terminal: string;
  sync_state: string;
  last_synced_at: string | null;
}

export interface CorporateGroup {
  id: string;
  name: string;
  code: string;
  active: boolean;
}

export interface Company {
  id: string;
  corporate_group_id: string;
  legal_name: string;
  trade_name: string | null;
  tax_id: string | null;
  employer_registration: string | null;
  timezone: string;
  address: BusinessAddress | null;
  active: boolean;
}

export interface BusinessAddress {
  street: string | null;
  exterior_number: string | null;
  interior_number: string | null;
  neighborhood: string | null;
  municipality: string | null;
  state: string | null;
  postal_code: string | null;
  country: string;
  reference_notes: string | null;
}

export interface Site {
  id: string;
  company_id: string;
  name: string;
  code: string;
  timezone: string;
  address: BusinessAddress | null;
  active: boolean;
}

export interface HardDeleteCaptcha {
  token: string;
  prompt: string;
  expires_in_seconds: number;
}

export interface Person {
  id: string;
  corporate_group_id: string;
  first_name: string;
  last_name: string;
  second_last_name: string | null;
  preferred_name: string | null;
  email: string | null;
  phone: string | null;
  birth_date: string | null;
  sex: string | null;
  marital_status: string | null;
  nationality: string | null;
  birth_state: string | null;
  address_street: string | null;
  address_ext_number: string | null;
  address_int_number: string | null;
  address_neighborhood: string | null;
  address_municipality: string | null;
  address_state: string | null;
  postal_code: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relationship: string | null;
  active: boolean;
}

export interface PersonSensitiveIdentifiers {
  curp: string | null;
  rfc: string | null;
  nss: string | null;
  fiscal_name: string | null;
  tax_regime: string | null;
  fiscal_postal_code: string | null;
}

export interface PersonPhoto {
  content_type: string;
  size_bytes: number;
  updated_at: string;
}

export interface Employment {
  id: string;
  person_id: string;
  company_id: string;
  site_id: string | null;
  employee_number: string;
  position: string | null;
  department: string | null;
  cost_center: string | null;
  manager_person_id: string | null;
  contract_type: string | null;
  employment_relation_type: string | null;
  job_category: string | null;
  work_location: string | null;
  started_on: string;
  ended_on: string | null;
  probation_ends_on: string | null;
  active: boolean;
}

export interface EmploymentCompensation {
  employment_id: string;
  daily_salary: string | null;
  integrated_daily_salary: string | null;
  pay_frequency: string | null;
  payment_method: string | null;
  bank_clabe: string | null;
  imss_umf: string | null;
  imss_worker_type: string | null;
  imss_salary_type: string | null;
  imss_workday_type: string | null;
}

export interface ScheduleSlot {
  id: string;
  work_schedule_id: string;
  day_of_week: number;
  kind: "entry" | "meal_out" | "meal_in" | "exit";
  sequence: number;
  expected_at: string;
  window_start: string | null;
  window_end: string | null;
  tolerance_minutes: number;
  required: boolean;
}

export interface WorkSchedule {
  id: string;
  company_id: string;
  name: string;
  timezone: string;
  automatic_exit_enabled: boolean;
  version: number;
  active: boolean;
  slots: ScheduleSlot[];
}

export interface ScheduleAssignment {
  id: string;
  employment_id: string;
  work_schedule_id: string;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
}

export interface Holiday {
  id: string;
  company_id: string;
  holiday_date: string;
  name: string;
  kind: "statutory" | "company" | "electoral";
  source: string | null;
  is_paid_rest: boolean;
  generated: boolean;
}

export interface EnrollmentRequest {
  id: string;
  person_id: string;
  worker_name: string;
  employment_id: string;
  employee_number: string;
  company_name: string;
  site_name: string | null;
  position: string | null;
  device_id: string;
  methods: string[];
  fingerprint_positions: string[];
  status: string;
  requested_by: string | null;
  approved_by: string | null;
  completed_by: string | null;
  identity_verified_by: string | null;
  identity_verified_at: string | null;
  identity_verification_reference: string | null;
  consent_recorded_by: string | null;
  consent_recorded_at: string | null;
  consent_reference: string | null;
  note: string | null;
}

export interface EnrollmentCandidate {
  person_id: string;
  worker_name: string;
  employment_id: string;
  employee_number: string;
  company_id: string;
  company_name: string;
  site_name: string | null;
  position: string | null;
}

export interface DeviceCommand {
  id: string;
  device_id: string;
  protocol_command_id: number;
  command_type: string;
  command: string;
  status: string;
  return_code: number | null;
  queued_at: string;
  sent_at: string | null;
  confirmed_at: string | null;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  roles: string[];
  corporate_group_ids: string[];
  company_ids: string[];
  last_login_at: string | null;
}

export interface AuditEntry {
  action: string;
  user_id: string | null;
  resource_type: string | null;
  request_id: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface DeviceEvent {
  type: string;
  severity: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Me {
  user: AdminUser;
  permissions: string[];
}
