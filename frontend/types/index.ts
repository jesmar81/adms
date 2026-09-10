export interface Device {
  id: string;
  serial_number: string;
  name: string | null;
  model: string | null;
  firmware_version: string | null;
  platform: string | null;
  ip_address: string | null;
  mac_address: string | null;
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

export interface DeviceUser {
  id: string;
  device_id: string;
  pin: string;
  name: string;
  privilege: number;
  card_number: string | null;
  enabled: boolean;
  sync_state: string;
  last_protocol_command_id: number | null;
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
