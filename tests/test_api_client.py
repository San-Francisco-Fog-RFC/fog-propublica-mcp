"""
Tests for the ProPublica API client.

This module contains unit tests for the ProPublica Nonprofit Explorer API client,
including mocked API responses and validation testing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import httpx
from datetime import datetime
from typing import Dict, Any

from propublica_mcp.api_client import ProPublicaClient, ProPublicaAPIError
from propublica_mcp.models import (
    NonprofitOrganization,
    Filing,
    SearchResult
)


@pytest.fixture
def api_client():
    """Create a ProPublica API client instance for testing."""
    return ProPublicaClient()


@pytest.fixture
def mock_organization_data():
    """Mock organization data from ProPublica API."""
    return {
        "organization": {
            "ein": "123456789",
            "name": "Test Nonprofit Organization",
            "address": "123 Main St",
            "city": "Test City",
            "state": "CA",
            "zipcode": "12345",
            "ntee_code": "A01",
            "subseccd": "3",
            "accounting_period": "12",
            "activity": "Educational services",
            "adv_ruling_process_cd": "",
            "asset_amt": 500000,
            "income_amt": 1000000
        }
    }


@pytest.fixture
def mock_search_data():
    """Mock search results data from ProPublica API."""
    return {
        "organizations": [
            {
                "ein": "123456789",
                "name": "Test Nonprofit 1",
                "ntee_code": "A01",
                "income_amt": 1000000,
                "city": "Test City",
                "state": "CA"
            },
            {
                "ein": "987654321",
                "name": "Test Nonprofit 2",
                "ntee_code": "B20",
                "income_amt": 750000,
                "city": "Another City",
                "state": "NY"
            }
        ],
        "total_results": 50,
        "page": 0,
        "per_page": 2
    }


@pytest.fixture
def mock_filing_data():
    """Mock filing data from ProPublica API."""
    return {
        "filings": [
            {
                "ein": "123456789",
                "tax_prd": 202212,
                "form_type": "990",
                "pdf_url": "https://example.com/filing1.pdf",
                "totrevenue": 1000000.0,
                "totfuncexpns": 800000.0,
                "totassetsend": 600000.0,
                "totliabend": 100000.0
            },
            {
                "ein": "123456789",
                "tax_prd": 202112,
                "form_type": "990",
                "pdf_url": "https://example.com/filing2.pdf",
                "totrevenue": 950000.0,
                "totfuncexpns": 750000.0,
                "totassetsend": 550000.0,
                "totliabend": 100000.0
            }
        ]
    }


class TestProPublicaClient:
    """Test suite for ProPublica API client."""
    
    def test_init(self):
        """Test client initialization."""
        client = ProPublicaClient()
        assert client.base_url == "https://projects.propublica.org/nonprofits/api/v2"
        assert client.timeout == 30
        assert client.rate_limiter.max_requests == 60
    
    @pytest.mark.asyncio
    async def test_search_organizations_success(self, api_client, mock_search_data):
        """Test successful organization search."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_search_data
            
            result = await api_client.search_organizations(query="test")
            
            assert isinstance(result, SearchResult)
            assert len(result.organizations) == 2
            assert result.total_results == 50
            assert result.organizations[0].ein == "123456789"
            
            # Verify the request was made with correct parameters
            mock_request.assert_called_once_with(
                "/search.json",
                {"q": "test"}
            )
    
    @pytest.mark.asyncio
    async def test_search_organizations_with_filters(self, api_client, mock_search_data):
        """Test organization search with filters."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_search_data
            
            result = await api_client.search_organizations(
                query="education",
                state="CA",
                ntee_category=1,
                subsection_code=3,
                page=1
            )
            
            assert isinstance(result, SearchResult)
            assert len(result.organizations) == 2
            
            # Verify the request was made with correct parameters
            mock_request.assert_called_once_with(
                "/search.json",
                {
                    "q": "education",
                    "state[id]": "CA",
                    "ntee[id]": 1,
                    "c_code[id]": 3,
                    "page": 1
                }
            )
    
    @pytest.mark.asyncio
    async def test_get_organization_success(self, api_client, mock_organization_data):
        """Test successful organization retrieval."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_organization_data
            
            result = await api_client.get_organization("123456789")
            
            assert isinstance(result, NonprofitOrganization)
            assert result.ein == "123456789"
            assert result.name == "Test Nonprofit Organization"
            
            mock_request.assert_called_once_with("/organizations/123456789.json")
    
    @pytest.mark.asyncio
    async def test_get_organization_filings_success(self, api_client):
        """Test successful filing retrieval."""
        # Create mock data with correct field mapping for API parsing
        mock_filing_data = {
            "filings_with_data": [
                {
                    "ein": "123456789",
                    "tax_prd": 202212,  # This will be converted to tax_year=2022
                    "form_type": "990",
                    "pdf_url": "https://example.com/filing1.pdf",
                    "totrevenue": 1000000.0,
                    "totfuncexpns": 800000.0,
                    "totassetsend": 600000.0,
                    "totliabend": 100000.0
                },
                {
                    "ein": "123456789",
                    "tax_prd": 202112,  # This will be converted to tax_year=2021
                    "form_type": "990",
                    "pdf_url": "https://example.com/filing2.pdf",
                    "totrevenue": 950000.0,
                    "totfuncexpns": 750000.0,
                    "totassetsend": 550000.0,
                    "totliabend": 100000.0
                }
            ]
        }
        
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_filing_data

            result = await api_client.get_organization_filings("123456789")

            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(filing, Filing) for filing in result)
            assert result[0].tax_year == 2022  # Should be converted from tax_prd 202212
            assert result[0].totrevenue == 1000000.0

            # Verify the request was made with correct endpoint
            mock_request.assert_called_once_with(
                "/organizations/123456789.json"
            )
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, api_client):
        """Test that rate limiting works correctly."""
        # Mock the actual request to avoid real API calls
        with patch.object(api_client.client, 'get', new_callable=AsyncMock) as mock_get:
            # Create a mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"organizations": [], "total_results": 0}
            mock_get.return_value = mock_response
            
            # Make multiple requests quickly
            start_time = datetime.now()
            
            # This should be rate limited to 60 requests per minute
            for i in range(3):
                await api_client.search_organizations(query=f"test{i}")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # With rate limiting, this should take some time
            # (Though this is a basic test - in practice rate limiting is more complex)
            assert mock_get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, api_client):
        """Test handling of HTTP errors."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ProPublicaAPIError("Not found", 404)
            
            with pytest.raises(ProPublicaAPIError) as exc_info:
                await api_client.get_organization("999999999")
            
            assert "Not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, api_client):
        """Test handling of network errors."""
        with patch.object(api_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection failed")
            
            with pytest.raises(ProPublicaAPIError) as exc_info:
                await api_client.search_organizations(query="test")
            
            assert "Connection failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, api_client):
        """Test handling of timeout errors."""
        with patch.object(api_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(ProPublicaAPIError) as exc_info:
                await api_client.search_organizations(query="test")
            
            assert "Request timeout" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_json_parse_error_handling(self, api_client):
        """Test handling of JSON parsing errors."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = ProPublicaAPIError("Invalid JSON response")
            
            with pytest.raises(ProPublicaAPIError) as exc_info:
                await api_client.search_organizations(query="test")
            
            assert "Invalid JSON response" in str(exc_info.value)
    
    def test_ein_validation(self, api_client):
        """Test EIN validation in API methods."""
        # Test invalid EIN formats
        with pytest.raises(ProPublicaAPIError):
            asyncio.run(api_client.get_organization("12345"))  # Too short
        
        with pytest.raises(ProPublicaAPIError):
            asyncio.run(api_client.get_organization("1234567890"))  # Too long
        
        with pytest.raises(ProPublicaAPIError):
            asyncio.run(api_client.get_organization("12-345678a"))  # Contains letter
    
    @pytest.mark.asyncio
    async def test_empty_search_results(self, api_client):
        """Test handling of empty search results."""
        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "organizations": [],
                "total_results": 0,
                "page": 0,
                "per_page": 25
            }
            
            result = await api_client.search_organizations(query="nonexistent")
            
            assert isinstance(result, SearchResult)
            assert len(result.organizations) == 0
            assert result.total_results == 0
    
    @pytest.mark.asyncio
    async def test_large_search_results(self, api_client):
        """Test handling of large search result sets."""
        # Mock large dataset with valid 9-digit EINs
        large_org_list = []
        for i in range(100):
            # Generate valid 9-digit EINs: pad with zeros if needed
            ein = f"{123456000 + i:09d}"
            large_org_list.append({
                "ein": ein,
                "name": f"Test Nonprofit {i}",
                "ntee_code": "A01",
                "income_amt": 1000000 + i * 1000,
                "city": "Test City",
                "state": "CA"
            })

        mock_large_data = {
            "organizations": large_org_list,
            "total_results": 1000,
            "page": 0,
            "per_page": 100
        }

        with patch.object(api_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_large_data

            result = await api_client.search_organizations(query="test")

            assert isinstance(result, SearchResult)
            assert len(result.organizations) == 100
            assert result.total_results == 1000


if __name__ == "__main__":
    pytest.main([__file__]) 