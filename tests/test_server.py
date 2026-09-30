"""
Tests for the ProPublica MCP server.

This module contains unit tests for the MCP server tools,
including mocked API responses and tool validation testing.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

# Import the server tools directly
from src.propublica_mcp.server import (
    search_nonprofits,
    get_organization,
    get_organization_filings,
    analyze_nonprofit_financials,
    search_similar_nonprofits,
    export_nonprofit_data
)

from src.propublica_mcp.models import (
    NonprofitOrganization,
    Filing,
    SearchResult,
    FinancialSummary
)
from src.propublica_mcp.api_client import ProPublicaAPIError


@pytest.fixture
def mock_search_result():
    """Mock search result for testing."""
    org1 = NonprofitOrganization(
        ein="123456789",
        name="Test Nonprofit 1",
        state="CA",
        ntee_code="A01",
        city="Test City",
        address="123 Main St",
        zipcode="12345",
        subseccd="3"
    )
    
    return SearchResult(
        total_results=1,
        num_pages=1,
        cur_page=0,
        per_page=25,
        page_offset=0,
        organizations=[org1]
    )


@pytest.fixture
def mock_organization():
    """Mock organization for testing."""
    return NonprofitOrganization(
        ein="123456789",
        name="Test Nonprofit",
        address="123 Main St",
        city="Test City",
        state="CA",
        zipcode="12345",
        subseccd="3",
        ntee_code="A01"
    )


@pytest.fixture
def mock_filings():
    """Mock filings for testing."""
    return [
        Filing(
            ein="123456789",
            tax_year=2022,
            form_type="990",
            pdf_url="https://example.com/filing1.pdf",
            totrevenue=1000000.0,
            totfuncexpns=800000.0,
            totassetsend=600000.0,
            totliabend=100000.0
        ),
        Filing(
            ein="123456789",
            tax_year=2021,
            form_type="990",
            pdf_url="https://example.com/filing2.pdf",
            totrevenue=950000.0,
            totfuncexpns=750000.0,
            totassetsend=550000.0,
            totliabend=100000.0
        )
    ]


class TestServerTools:
    """Test suite for MCP server tools."""
    
    @pytest.mark.asyncio
    async def test_search_nonprofits_basic(self, mock_search_result):
        """Test basic nonprofit search functionality."""
        with patch('src.propublica_mcp.server.api_client.search_organizations', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_search_result
            
            result = await search_nonprofits(query="education")
            result_data = json.loads(result)
            
            assert "organizations" in result_data
            assert "pagination" in result_data
            assert "search_metadata" in result_data
            assert len(result_data["organizations"]) == 1
            assert result_data["organizations"][0]["ein"] == "123456789"
            assert result_data["search_query"] == "education"
            assert "generated_at" in result_data
            
            mock_search.assert_called_once_with(
                query="education",
                state=None,
                ntee_category=None,
                subsection_code=None,
                page=0,
                limit=25
            )
    
    @pytest.mark.asyncio
    async def test_search_nonprofits_with_filters(self, mock_search_result):
        """Test nonprofit search with filters."""
        with patch('src.propublica_mcp.server.api_client.search_organizations', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_search_result
            
            result = await search_nonprofits(
                query="health",
                state="CA",
                ntee_code="4",
                subsection_code="3",
                page=1,
                per_page=10
            )
            result_data = json.loads(result)
            
            assert result_data["filters"]["state"] == "CA"
            assert result_data["filters"]["ntee_code"] == "4"
            assert result_data["filters"]["subsection_code"] == "3"
            assert result_data["pagination"]["page"] == 1
            assert result_data["pagination"]["per_page"] == 10
            
            mock_search.assert_called_once_with(
                query="health",
                state="CA",
                ntee_category=4,
                subsection_code=3,
                page=1,
                limit=10
            )
    
    @pytest.mark.asyncio
    async def test_search_nonprofits_invalid_state(self):
        """Test search with invalid state code."""
        result = await search_nonprofits(query="test", state="XX")
        result_data = json.loads(result)
        
        assert "error" in result_data
        assert "Invalid state code" in result_data["error"]
    
    @pytest.mark.asyncio
    async def test_get_organization_success(self, mock_organization):
        """Test successful organization retrieval."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_organization
            
            result = await get_organization(ein="123456789")
            result_data = json.loads(result)
            
            assert "organization" in result_data
            assert result_data["organization"]["ein"] == "123456789"
            assert result_data["organization"]["name"] == "Test Nonprofit"
            assert "retrieved_at" in result_data
            
            mock_get.assert_called_once_with("123456789")
    
    @pytest.mark.asyncio
    async def test_get_organization_invalid_ein(self):
        """Test organization retrieval with invalid EIN."""
        result = await get_organization(ein="invalid")
        result_data = json.loads(result)
        
        assert "error" in result_data
        assert "Invalid EIN format" in result_data["error"]
    
    @pytest.mark.asyncio
    async def test_get_organization_ein_with_hyphen(self, mock_organization):
        """Test organization retrieval with hyphenated EIN."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_organization
            
            result = await get_organization(ein="12-3456789")
            result_data = json.loads(result)
            
            assert "organization" in result_data
            # Should clean the EIN and call with clean version
            mock_get.assert_called_once_with("123456789")
    
    @pytest.mark.asyncio
    async def test_get_organization_filings_success(self, mock_filings):
        """Test successful filing retrieval."""
        with patch('src.propublica_mcp.server.api_client.get_organization_filings', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_filings
            
            result = await get_organization_filings(ein="123456789")
            result_data = json.loads(result)
            
            assert "filings" in result_data
            assert "filing_summary" in result_data
            assert len(result_data["filings"]) == 2
            assert result_data["filings"][0]["tax_year"] == 2022
    
    @pytest.mark.asyncio
    async def test_get_organization_filings_limit(self, mock_filings):
        """Test filing retrieval with limit."""
        # Create more filings to test limiting
        extended_filings = mock_filings + [
            Filing(
                ein="123456789",
                tax_year=2020,
                form_type="990",
                pdf_url="https://example.com/filing3.pdf",
                totrevenue=900000.0,
                totfuncexpns=700000.0,
                totassetsend=500000.0,
                totliabend=90000.0
            )
        ]
        
        with patch('src.propublica_mcp.server.api_client.get_organization_filings', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = extended_filings
            
            result = await get_organization_filings(ein="123456789", limit=2)
            result_data = json.loads(result)
            
            assert len(result_data["filings"]) == 2
            assert result_data["total_filings_available"] == 3
            assert result_data["filings_returned"] == 2
    
    @pytest.mark.asyncio
    async def test_analyze_nonprofit_financials_success(self, mock_organization, mock_filings):
        """Test financial analysis tool."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get_org:
            with patch('src.propublica_mcp.server.api_client.get_organization_filings', new_callable=AsyncMock) as mock_get_filings:
                mock_get_org.return_value = mock_organization
                mock_get_filings.return_value = mock_filings
                
                result = await analyze_nonprofit_financials(ein="123456789", years=2)
                result_data = json.loads(result)
                
                assert "financial_summary" in result_data
                assert "detailed_data" in result_data
                assert "trends" in result_data
                assert "ratios" in result_data
                
                summary = result_data["financial_summary"]
                assert summary["ein"] == "123456789"
                assert summary["organization_name"] == "Test Nonprofit"
                assert "filings_analyzed" in summary
    
    @pytest.mark.asyncio
    async def test_search_similar_nonprofits_success(self, mock_organization, mock_search_result):
        """Test similar nonprofits search."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get_org:
            with patch('src.propublica_mcp.server.api_client.search_organizations', new_callable=AsyncMock) as mock_search:
                mock_get_org.return_value = mock_organization
                mock_search.return_value = mock_search_result
                
                result = await search_similar_nonprofits(
                    ein="123456789",
                    same_ntee=True,
                    min_revenue=500000,
                    max_revenue=2000000,
                    limit=5
                )
                result_data = json.loads(result)
                
                assert "similar_organizations" in result_data
                assert "reference_organization" in result_data
                assert "search_criteria" in result_data
                assert result_data["reference_organization"]["ein"] == "123456789"
    
    @pytest.mark.asyncio
    async def test_export_nonprofit_data_json(self, mock_organization, mock_filings):
        """Test nonprofit data export in JSON format."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get_org:
            with patch('src.propublica_mcp.server.api_client.get_organization_filings', new_callable=AsyncMock) as mock_get_filings:
                mock_get_org.return_value = mock_organization
                mock_get_filings.return_value = mock_filings
                
                result = await export_nonprofit_data(
                    eins=["123456789"],
                    format="json",
                    include_financials=True,
                    include_filings=True,
                    max_filings_per_org=2
                )
                result_data = json.loads(result)
                
                assert "organizations" in result_data
                assert "metadata" in result_data
                assert len(result_data["organizations"]) == 1
                
                org_data = result_data["organizations"][0]
                assert org_data["ein"] == "123456789"
                assert "organization_name" in org_data
                assert "recent_filings" in org_data
    
    @pytest.mark.asyncio
    async def test_export_nonprofit_data_csv(self, mock_organization):
        """Test nonprofit data export in CSV format."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get_org:
            mock_get_org.return_value = mock_organization
            
            result = await export_nonprofit_data(
                eins=["123456789"],
                format="csv",
                include_financials=False,
                include_filings=False
            )
            result_data = json.loads(result)
            
            assert "csv_data" in result_data
            assert "export_metadata" in result_data
            
            # CSV should contain headers and data
            csv_content = result_data["csv_data"]
            assert "ein,organization_name" in csv_content
            assert "123456789,Test Nonprofit" in csv_content
    
    @pytest.mark.asyncio
    async def test_export_nonprofit_data_invalid_format(self):
        """Test export with invalid format."""
        result = await export_nonprofit_data(
            eins=["123456789"],
            format="invalid"
        )
        result_data = json.loads(result)
        
        assert "error" in result_data
        assert "Invalid format" in result_data["error"]
    
    @pytest.mark.asyncio
    async def test_error_handling_api_failure(self):
        """Test error handling when API calls fail."""
        with patch('src.propublica_mcp.server.api_client.search_organizations', new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = Exception("API connection failed")
            
            result = await search_nonprofits(query="test")
            result_data = json.loads(result)
            
            assert "error" in result_data
            assert "Search failed" in result_data["error"]
            assert "error_type" in result_data
    
    @pytest.mark.asyncio
    async def test_pagination_limits(self, mock_search_result):
        """Test pagination and limit handling."""
        with patch('src.propublica_mcp.server.api_client.search_organizations', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_search_result
            
            # Test per_page limit (should cap at 25)
            result = await search_nonprofits(query="test", per_page=100)
            result_data = json.loads(result)
            
            assert result_data["pagination"]["per_page"] == 25
            
            # Verify the API was called with the capped value
            call_args = mock_search.call_args
            assert call_args[1]["limit"] == 25
    
    @pytest.mark.asyncio
    async def test_filing_limit_validation(self, mock_filings):
        """Test filing retrieval limit validation."""
        with patch('src.propublica_mcp.server.api_client.get_organization_filings', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_filings
            
            # Test limit over 100 (should cap at 100)
            result = await get_organization_filings(ein="123456789", limit=150)
            result_data = json.loads(result)
            
            # The limit should be applied in the function
            assert "filings" in result_data
    
    @pytest.mark.asyncio
    async def test_ein_cleaning_and_validation(self, mock_organization):
        """Test EIN cleaning and validation across tools."""
        with patch('src.propublica_mcp.server.api_client.get_organization', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_organization
            
            # Test various EIN formats
            test_eins = [
                "123456789",      # Clean
                "12-3456789",     # With hyphen
                " 123456789 ",    # With spaces
            ]
            
            for ein in test_eins:
                result = await get_organization(ein=ein)
                result_data = json.loads(result)
                
                assert "organization" in result_data
                # Should always call with clean EIN
                mock_get.assert_called_with("123456789")
            
            # Test invalid EINs
            invalid_eins = [
                "12345678",       # Too short
                "1234567890",     # Too long
                "abcdefghi",      # Not numeric
                "",               # Empty
            ]
            
            for ein in invalid_eins:
                result = await get_organization(ein=ein)
                result_data = json.loads(result)
                
                assert "error" in result_data
                assert "Invalid EIN format" in result_data["error"]


if __name__ == "__main__":
    pytest.main([__file__]) 