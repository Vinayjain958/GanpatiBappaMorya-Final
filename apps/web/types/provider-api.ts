/** Shapes returned/accepted by the provider-facing API. Mirrors
 * apps/api/src/schemas/provider.py, experience_write.py, availability.py. */

export interface ProviderMe {
  id: string;
  business_name: string;
  description: string | null;
  provider_type: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  website: string | null;
  verification_status: string;
  city: string | null;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderUpdateInput {
  business_name?: string;
  description?: string;
  provider_type?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  city?: string;
}

export interface OpeningHourInput {
  day_of_week: number;
  open_time?: string | null;
  close_time?: string | null;
  is_closed?: boolean;
}

export interface LocationInput {
  latitude: number;
  longitude: number;
  place_name?: string;
  address?: string;
  locality?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
}

export interface ExperienceCreateInput {
  title: string;
  short_description: string;
  full_description: string;
  category_id: string;
  location: LocationInput;
  currency?: string;
  price?: number | null;
  minimum_price?: number | null;
  maximum_price?: number | null;
  price_type?: "fixed" | "range" | "free" | "unknown";
  duration_minutes?: number | null;
  minimum_group_size?: number | null;
  maximum_group_size?: number | null;
  capacity?: number | null;
  wheelchair_accessible?: boolean | null;
  step_free?: boolean | null;
  accessibility_notes?: string | null;
  suitability?: string[];
  tags?: string[];
  status?: "active" | "draft" | "inactive";
  opening_hours?: OpeningHourInput[];
}

export type ExperienceUpdateInput = Partial<Omit<ExperienceCreateInput, "location">>;

export interface AvailabilityInput {
  starts_at: string;
  ends_at: string;
  capacity: number;
  available_slots?: number | null;
}

export interface AvailabilityUpdateInput {
  starts_at?: string;
  ends_at?: string;
  capacity?: number;
  available_slots?: number | null;
  status?: "active" | "cancelled" | "inactive";
}

export interface AvailabilitySlot {
  id: string;
  experience_id: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  available_slots: number | null;
  status: string;
}
