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

export interface AttendanceRow {
  id: string;
  device_id: string;
  device_user_pin: string;
  recorded_at: string;
  status: number;
  verify_mode: number;
  work_code: string | null;
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
  active: boolean;
}

export interface Site {
  id: string;
  company_id: string;
  name: string;
  code: string;
  timezone: string;
  address: string | null;
  active: boolean;
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
  active: boolean;
}

export interface Employment {
  id: string;
  person_id: string;
  company_id: string;
  employee_number: string;
  position: string | null;
  department: string | null;
  cost_center: string | null;
  manager_person_id: string | null;
  contract_type: string | null;
  started_on: string;
  ended_on: string | null;
  active: boolean;
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
  version: number;
  active: boolean;
  slots: ScheduleSlot[];
}

export interface EnrollmentRequest {
  id: string;
  employment_id: string;
  device_id: string;
  methods: string[];
  status: string;
  requested_by: string | null;
  approved_by: string | null;
  completed_by: string | null;
  note: string | null;
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
