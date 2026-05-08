"""
API tests for Context Market
Run with: pytest tests/test_api.py
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestAgentRegistration:
    def test_register_agent(self):
        """Agent can register and receives API key"""
        response = client.post("/agent/register", json={"name": "Test Agent"})
        assert response.status_code == 201
        data = response.json()
        assert "agent_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("acp_")
        
    def test_register_missing_name(self):
        """Registration fails without name"""
        response = client.post("/agent/register", json={})
        assert response.status_code == 422

class TestMemoryOperations:
    def test_store_memory_unauthorized(self):
        """Memory storage requires API key"""
        response = client.post("/memory/store", json={
            "title": "Test",
            "category": "test",
            "knowledge_text": "Test knowledge",
            "price_per_query": 0.10
        })
        assert response.status_code == 401

    def test_list_memory(self):
        """Memory listing returns array"""
        # First register to get API key
        reg = client.post("/agent/register", json={"name": "List Test"})
        api_key = reg.json()["api_key"]
        
        response = client.get("/memory/list", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

class TestQueryFlow:
    def test_query_insufficient_credits(self):
        """Query fails with 402 when buyer has no credits"""
        # Register buyer
        buyer = client.post("/agent/register", json={"name": "Buyer"})
        buyer_key = buyer.json()["api_key"]
        
        # Register seller and create listing
        seller = client.post("/agent/register", json={"name": "Seller"})
        seller_key = seller.json()["api_key"]
        
        store = client.post("/memory/store", 
            headers={"X-API-Key": seller_key},
            json={
                "title": "Test Knowledge",
                "category": "test",
                "knowledge_text": "This is test knowledge for querying.",
                "price_per_query": 0.10
            }
        )
        listing_id = store.json()["listing_id"]
        
        # Query without credits should fail
        response = client.post("/memory/query",
            headers={"X-API-Key": buyer_key},
            json={"listing_id": listing_id, "question": "What is this?"}
        )
        assert response.status_code == 402

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
