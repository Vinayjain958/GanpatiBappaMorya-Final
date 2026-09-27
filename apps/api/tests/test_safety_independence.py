import pytest
from unittest.mock import patch
from fastapi import status
from .test_safety import register_traveler, auth_header

def test_safety_independence(client):
    # We will mock out the core discovery/ranking services completely
    # and assert safety still works.
    with patch("src.services.discovery_pipeline.DiscoveryPipelineService") as MockDiscovery, \
         patch("src.services.ranking.PersonalizedRankingService") as MockRanking, \
         patch("src.services.feasibility.FeasibilityService") as MockFeasibility:
        
        # Make them raise exceptions if called
        MockDiscovery.side_effect = Exception("Discovery should not be called")
        MockRanking.side_effect = Exception("Ranking should not be called")
        MockFeasibility.side_effect = Exception("Feasibility should not be called")

        user_data = register_traveler(client, email="traveler4@test.com")
        headers = auth_header(user_data)

        # 1. Test contacts
        response = client.post("/api/v1/safety/emergency-contacts", json={
            "name": "Fallback Test",
            "phone": "911",
            "is_primary": True
        }, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED

        # 2. Test nearby resources
        response = client.get("/api/v1/safety/resources/nearby?lat=40.7128&lng=-74.0060", headers=headers)
        assert response.status_code == status.HTTP_200_OK

        # 3. Test alerts
        response = client.post("/api/v1/safety/emergency-alerts", json={
            "trigger_source": "test_independence",
            "idempotency_key": "test_independence_key"
        }, headers=headers)
        assert response.status_code == status.HTTP_201_CREATED
