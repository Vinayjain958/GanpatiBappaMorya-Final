import { apiClient } from "./client";
import type { 
  EmergencyContact, 
  EmergencyContactCreate, 
  EmergencyContactUpdate,
  SafetyResource,
  EmergencyAlert,
  EmergencyAlertCreate
} from "@/types/safety";

export async function getEmergencyContacts(): Promise<EmergencyContact[]> {
  return apiClient.get<EmergencyContact[]>("/api/v1/safety/emergency-contacts");
}

export async function createEmergencyContact(data: EmergencyContactCreate): Promise<EmergencyContact> {
  return apiClient.post<EmergencyContact>("/api/v1/safety/emergency-contacts", data);
}

export async function updateEmergencyContact(id: string, data: EmergencyContactUpdate): Promise<EmergencyContact> {
  return apiClient.patch<EmergencyContact>(`/api/v1/safety/emergency-contacts/${id}`, data);
}

export async function deleteEmergencyContact(id: string): Promise<void> {
  return apiClient.delete<void>(`/api/v1/safety/emergency-contacts/${id}`);
}

export async function getNearbySafetyResources(
  lat: number, 
  lng: number, 
  radiusKm = 5,
  category?: string
): Promise<SafetyResource[]> {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lng: lng.toString(),
    radius_km: radiusKm.toString()
  });
  if (category) {
    params.append("category", category);
  }
  return apiClient.get<SafetyResource[]>(`/api/v1/safety/resources/nearby?${params.toString()}`);
}

export async function createEmergencyAlert(data: EmergencyAlertCreate): Promise<EmergencyAlert> {
  return apiClient.post<EmergencyAlert>("/api/v1/safety/emergency-alerts", data);
}

export async function getEmergencyAlerts(): Promise<EmergencyAlert[]> {
  return apiClient.get<EmergencyAlert[]>("/api/v1/safety/emergency-alerts");
}

export async function cancelEmergencyAlert(id: string): Promise<EmergencyAlert> {
  return apiClient.post<EmergencyAlert>(`/api/v1/safety/emergency-alerts/${id}/cancel`);
}
