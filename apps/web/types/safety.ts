export interface EmergencyContact {
  id: string;
  traveler_id: string;
  name: string;
  phone: string;
  relationship?: string;
  priority: number;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmergencyContactCreate {
  name: string;
  phone: string;
  relationship?: string;
  priority?: number;
  is_primary?: boolean;
  is_active?: boolean;
}

export interface EmergencyContactUpdate {
  name?: string;
  phone?: string;
  relationship?: string;
  priority?: number;
  is_primary?: boolean;
  is_active?: boolean;
}

export interface SafetyResource {
  id: string;
  type: "hospital" | "police" | "consulate";
  name: string;
  latitude: number;
  longitude: number;
  address?: string;
  phone?: string;
  website?: string;
  distance_km?: number;
  source: string;
  is_synthetic: boolean;
  retrieved_at: string;
}

export interface EmergencyAlert {
  id: string;
  traveler_id: string;
  status: "TRIGGERED" | "DISPATCHED" | "ACKNOWLEDGED" | "CANCELLED" | "FAILED";
  created_at: string;
  acknowledged_at?: string;
  cancelled_at?: string;
  trigger_source: string;
  message?: string;
  latitude?: number;
  longitude?: number;
  location_shared: boolean;
  delivery_status: string;
  idempotency_key: string;
}

export interface EmergencyAlertCreate {
  trigger_source: string;
  message?: string;
  latitude?: number;
  longitude?: number;
  location_shared?: boolean;
  idempotency_key: string;
}
