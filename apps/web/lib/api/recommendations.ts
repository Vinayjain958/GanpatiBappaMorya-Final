import { RecommendationRequest, RecommendationResponse } from "@/types/api";
import { apiClient } from "./client";

export const recommendationApi = {
  getRecommendations: async (request: RecommendationRequest): Promise<RecommendationResponse> => {
    return apiClient.post("/api/v1/recommendations", request);
  },
};
