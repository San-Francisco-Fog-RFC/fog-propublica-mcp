"""ProPublica Nonprofit Explorer API client."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urlencode

import httpx
import structlog
import sys
from pydantic import ValidationError

from .models import (
    NonprofitOrganization,
    Filing,
    SearchResult,
    US_STATES,
    NTEE_CATEGORIES,
    SUBSECTION_CODES
)

# Configure structlog to use stderr
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(30),  # INFO level
    logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ProPublicaAPIError(Exception):
    """Custom exception for ProPublica API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request."""
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            # Remove old requests outside the time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                # Wait until we can make another request
                oldest_request = min(self.requests)
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
            
            self.requests.append(now)


class ProPublicaClient:
    """Client for ProPublica Nonprofit Explorer API."""
    
    def __init__(
        self,
        base_url: str = "https://projects.propublica.org/nonprofits/api/v2",
        timeout: int = 30,
        max_requests_per_minute: int = 60,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(max_requests_per_minute, 60)
        
        # Configure HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "ProPublica-MCP-Server/1.0",
                "Accept": "application/json"
            },
            follow_redirects=True
        )
        
        logger.info("ProPublica API client initialized", base_url=base_url)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make an HTTP request with rate limiting and retries."""
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug("Making API request", url=url, params=params)
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            try:
                data = response.json()
                logger.debug("API request successful", status_code=response.status_code)
                return data
            except json.JSONDecodeError as e:
                raise ProPublicaAPIError(f"Invalid JSON response: {e}")
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and retry_count < self.max_retries:
                # Retry on server errors
                wait_time = 2 ** retry_count
                logger.warning(
                    f"Server error, retrying in {wait_time}s",
                    status_code=e.response.status_code,
                    retry_count=retry_count
                )
                await asyncio.sleep(wait_time)
                return await self._make_request(endpoint, params, retry_count + 1)
            
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            raise ProPublicaAPIError(error_msg, e.response.status_code)
        
        except httpx.RequestError as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.warning(
                    f"Request error, retrying in {wait_time}s",
                    error=str(e),
                    retry_count=retry_count
                )
                await asyncio.sleep(wait_time)
                return await self._make_request(endpoint, params, retry_count + 1)
            
            raise ProPublicaAPIError(f"Request failed: {e}")
    
    def _parse_organization(self, org_data: Dict[str, Any]) -> NonprofitOrganization:
        """Parse organization data from API response."""
        try:
            # Handle datetime parsing
            if org_data.get('updated'):
                try:
                    org_data['updated'] = datetime.fromisoformat(
                        org_data['updated'].replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    org_data['updated'] = None
            
            # Convert numeric fields to strings as expected by the model
            if org_data.get('ein'):
                if isinstance(org_data['ein'], int):
                    org_data['ein'] = str(org_data['ein']).zfill(9)  # Pad to 9 digits
                elif isinstance(org_data['ein'], str):
                    org_data['ein'] = org_data['ein'].zfill(9)  # Pad to 9 digits
            
            if org_data.get('subseccd') and isinstance(org_data['subseccd'], int):
                org_data['subseccd'] = str(org_data['subseccd'])
            
            return NonprofitOrganization(**org_data)
        except ValidationError as e:
            logger.error("Failed to parse organization data", error=str(e), data=org_data)
            raise ProPublicaAPIError(f"Invalid organization data: {e}")
    
    def _parse_filing(self, filing_data: Dict[str, Any]) -> Filing:
        """Parse filing data from API response."""
        try:
            # Convert numeric fields
            numeric_fields = ['totrevenue', 'totfuncexpns', 'totassetsend', 'totliabend']
            for field in numeric_fields:
                if field in filing_data and filing_data[field] is not None:
                    try:
                        filing_data[field] = float(filing_data[field])
                    except (ValueError, TypeError):
                        filing_data[field] = None
            
            # Handle tax year - convert from various formats
            if 'tax_prd_yr' in filing_data:
                filing_data['tax_year'] = filing_data.pop('tax_prd_yr')
            elif 'tax_prd' in filing_data and filing_data['tax_prd']:
                # Convert YYYYMM format to YYYY
                try:
                    tax_prd = str(filing_data.pop('tax_prd'))
                    if len(tax_prd) >= 4:
                        filing_data['tax_year'] = int(tax_prd[:4])
                except (ValueError, TypeError):
                    filing_data['tax_year'] = None
            
            # Handle form type - convert from API's integer codes to strings
            if 'formtype' in filing_data:
                form_type_code = filing_data.pop('formtype')
                filing_data['form_type'] = self._convert_form_type(form_type_code)
            elif 'form_type' in filing_data and isinstance(filing_data['form_type'], int):
                filing_data['form_type'] = self._convert_form_type(filing_data['form_type'])
            
            return Filing(**filing_data)
        except ValidationError as e:
            logger.error("Failed to parse filing data", error=str(e), data=filing_data)
            raise ProPublicaAPIError(f"Invalid filing data: {e}")
    
    def _convert_form_type(self, form_type_code) -> Optional[str]:
        """Convert ProPublica's form type codes to string names."""
        form_type_map = {
            0: "990",      # Form 990 
            1: "990EZ",    # Form 990-EZ
            2: "990PF",    # Form 990-PF (Private Foundation)
            3: "990T",     # Form 990-T (Unrelated Business Income Tax)
        }
        return form_type_map.get(form_type_code, "990")  # Default to 990
    
    def _has_valid_pdf(self, filing_data: Dict[str, Any]) -> bool:
        """Check if filing has a valid PDF URL."""
        pdf_url = filing_data.get('pdf_url')
        return pdf_url is not None and isinstance(pdf_url, str) and pdf_url.strip() != ""
    
    async def search_organizations(
        self,
        query: Optional[str] = None,
        state: Optional[str] = None,
        ntee_category: Optional[int] = None,
        subsection_code: Optional[int] = None,
        page: int = 0,
        limit: Optional[int] = None
    ) -> SearchResult:
        """
        Search for nonprofit organizations.
        
        Args:
            query: Search query string
            state: State abbreviation (e.g., 'NY', 'CA')
            ntee_category: NTEE category ID (1-10)
            subsection_code: 501(c) subsection code
            page: Page number (zero-indexed)
            limit: Maximum results per page (API default is 25)
        
        Returns:
            SearchResult with matching organizations
        """
        params = {}
        
        if query:
            params['q'] = query
        
        if page > 0:
            params['page'] = page
        
        if state:
            if state.upper() not in US_STATES:
                raise ProPublicaAPIError(f"Invalid state code: {state}")
            params['state[id]'] = state.upper()
        
        if ntee_category:
            if ntee_category not in NTEE_CATEGORIES:
                raise ProPublicaAPIError(f"Invalid NTEE category: {ntee_category}")
            params['ntee[id]'] = ntee_category
        
        if subsection_code:
            if subsection_code not in SUBSECTION_CODES:
                raise ProPublicaAPIError(f"Invalid subsection code: {subsection_code}")
            params['c_code[id]'] = subsection_code
        
        logger.info("Searching organizations", params=params)
        
        try:
            data = await self._make_request("/search.json", params)
            
            # Parse organizations
            organizations = []
            for org_data in data.get('organizations', []):
                try:
                    org = self._parse_organization(org_data)
                    organizations.append(org)
                except ProPublicaAPIError:
                    # Skip invalid organizations but continue processing
                    continue
            
            # Create search result
            search_result = SearchResult(
                total_results=data.get('total_results', 0),
                num_pages=data.get('num_pages', 0),
                cur_page=data.get('cur_page', 0),
                per_page=data.get('per_page', 25),
                page_offset=data.get('page_offset', 0),
                search_query=data.get('search_query'),
                selected_state=data.get('selected_state'),
                selected_ntee=data.get('selected_ntee'),
                selected_c_code=data.get('selected_c_code'),
                organizations=organizations
            )
            
            logger.info(
                "Search completed",
                total_results=search_result.total_results,
                organizations_found=len(organizations)
            )
            
            return search_result
        
        except Exception as e:
            logger.error("Search failed", error=str(e))
            raise
    
    async def get_organization(self, ein: str) -> NonprofitOrganization:
        """
        Get detailed organization information by EIN.
        
        Args:
            ein: Employer Identification Number
        
        Returns:
            NonprofitOrganization object
        """
        # Clean and validate EIN
        ein_clean = str(ein).replace('-', '').strip()
        if not ein_clean.isdigit() or len(ein_clean) != 9:
            raise ProPublicaAPIError(f"Invalid EIN format: {ein}")
        
        logger.info("Getting organization details", ein=ein_clean)
        
        try:
            data = await self._make_request(f"/organizations/{ein_clean}.json")
            
            if not data.get('organization'):
                raise ProPublicaAPIError(f"Organization not found: {ein}")
            
            org_data = data['organization'][0] if isinstance(data['organization'], list) else data['organization']
            organization = self._parse_organization(org_data)
            
            logger.info("Organization retrieved", name=organization.name, ein=ein_clean)
            return organization
        
        except Exception as e:
            logger.error("Failed to get organization", ein=ein_clean, error=str(e))
            raise
    
    async def get_organization_filings(
        self,
        ein: str,
        year: Optional[int] = None
    ) -> List[Filing]:
        """
        Get Form 990 filings for an organization.
        
        Args:
            ein: Employer Identification Number
            year: Optional tax year filter
        
        Returns:
            List of Filing objects
        """
        # Clean and validate EIN
        ein_clean = str(ein).replace('-', '').strip()
        if not ein_clean.isdigit() or len(ein_clean) != 9:
            raise ProPublicaAPIError(f"Invalid EIN format: {ein}")
        
        logger.info("Getting organization filings", ein=ein_clean, year=year)
        
        try:
            data = await self._make_request(f"/organizations/{ein_clean}.json")
            
            if not data.get('filings_with_data'):
                logger.warning("No filings found", ein=ein_clean)
                return []
            
            filings = []
            for filing_data in data['filings_with_data']:
                try:
                    filing_data['ein'] = ein_clean
                    filing = self._parse_filing(filing_data)
                    
                    # Apply year filter if specified
                    if year is None or filing.tax_year == year:
                        filings.append(filing)
                
                except ProPublicaAPIError:
                    # Skip invalid filings but continue processing
                    continue
            
            logger.info("Filings retrieved", ein=ein_clean, count=len(filings))
            return filings
        
        except Exception as e:
            logger.error("Failed to get filings", ein=ein_clean, error=str(e))
            raise
    
    async def search_by_name(self, name: str, limit: int = 10) -> List[NonprofitOrganization]:
        """
        Simple search by organization name.
        
        Args:
            name: Organization name to search for
            limit: Maximum number of results
        
        Returns:
            List of matching organizations
        """
        result = await self.search_organizations(query=name)
        return result.organizations[:limit]
    
    async def get_organization_summary(self, ein: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of an organization including basic info and recent filings.
        
        Args:
            ein: Employer Identification Number
        
        Returns:
            Dictionary with organization and filing summary
        """
        try:
            # Get organization details and recent filings concurrently
            org_task = self.get_organization(ein)
            filings_task = self.get_organization_filings(ein)
            
            organization, filings = await asyncio.gather(org_task, filings_task)
            
            # Sort filings by tax year (most recent first)
            filings.sort(key=lambda f: f.tax_year or 0, reverse=True)
            
            # Calculate basic financial metrics from most recent filing
            recent_filing = filings[0] if filings else None
            financial_summary = None
            
            if recent_filing:
                financial_summary = {
                    'most_recent_year': recent_filing.tax_year,
                    'total_revenue': recent_filing.totrevenue,
                    'total_expenses': recent_filing.totfuncexpns,
                    'total_assets': recent_filing.totassetsend,
                    'net_assets': recent_filing.net_assets,
                    'expense_ratio': recent_filing.expense_ratio
                }
            
            return {
                'organization': organization.dict(),
                'filing_years': [f.tax_year for f in filings if f.tax_year],
                'total_filings': len(filings),
                'financial_summary': financial_summary
            }
        
        except Exception as e:
            logger.error("Failed to get organization summary", ein=ein, error=str(e))
            raise
    
    async def get_most_recent_pdf_filing(self, ein: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent filing that has a PDF available for an organization.
        
        Iterates through all filings in reverse chronological order to find
        the newest filing with an actual PDF available.
        
        Args:
            ein: Employer Identification Number
        
        Returns:
            Dictionary with filing info and PDF URL if found, None otherwise
        """
        # Clean and validate EIN
        ein_clean = str(ein).replace('-', '').strip()
        if not ein_clean.isdigit() or len(ein_clean) != 9:
            raise ProPublicaAPIError(f"Invalid EIN format: {ein}")
        
        logger.info("Looking for most recent PDF filing", ein=ein_clean)
        
        try:
            data = await self._make_request(f"/organizations/{ein_clean}.json")
            
            if not data.get('filings_with_data'):
                logger.warning("No filings found", ein=ein_clean)
                return None
            
            # Sort filings by tax year (most recent first)
            filings = data['filings_with_data']
            filings_sorted = sorted(
                filings, 
                key=lambda f: f.get('tax_prd_yr', 0), 
                reverse=True
            )
            
            # Iterate through filings to find the most recent one with a PDF
            for filing in filings_sorted:
                if self._has_valid_pdf(filing):
                    pdf_info = {
                        'tax_year': filing.get('tax_prd_yr'),
                        'pdf_url': filing.get('pdf_url'),
                        'form_type': self._convert_form_type(filing.get('formtype', 0)),
                        'filing_date': filing.get('filing_date'),
                        'ein': ein_clean,
                        'organization_name': data.get('organization', [{}])[0].get('name', 'Unknown') if isinstance(data.get('organization'), list) else data.get('organization', {}).get('name', 'Unknown')
                    }
                    
                    logger.info(
                        "Found most recent PDF filing", 
                        ein=ein_clean, 
                        tax_year=pdf_info['tax_year'],
                        form_type=pdf_info['form_type']
                    )
                    return pdf_info
            
            logger.info("No PDF filings found", ein=ein_clean)
            return None
        
        except Exception as e:
            logger.error("Failed to get most recent PDF filing", ein=ein_clean, error=str(e))
            raise
    
    async def get_organizations_with_pdfs(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for organizations that have PDF filings available.
        
        Args:
            query: Search query string
            limit: Maximum number of organizations to return
        
        Returns:
            List of dictionaries with organization info and PDF availability
        """
        logger.info("Searching for organizations with PDFs", query=query, limit=limit)
        
        # Search for organizations
        search_result = await self.search_organizations(query=query)
        
        organizations_with_pdfs = []
        
        for org in search_result.organizations[:limit * 2]:  # Get more to filter down
            try:
                # Get detailed organization data to check for PDFs
                data = await self._make_request(f"/organizations/{org.ein}.json")
                
                filings_with_pdfs = []
                if data.get('filings_with_data'):
                    for filing in data['filings_with_data']:
                        if self._has_valid_pdf(filing):
                            filings_with_pdfs.append({
                                'tax_year': filing.get('tax_prd_yr'),
                                'pdf_url': filing.get('pdf_url'),
                                'form_type': self._convert_form_type(filing.get('formtype', 0))
                            })
                
                if filings_with_pdfs:  # Only include orgs with actual PDFs
                    org_info = {
                        'organization': org.dict(),
                        'pdf_filings_count': len(filings_with_pdfs),
                        'recent_pdfs': filings_with_pdfs[:3],  # Most recent 3
                        'have_pdfs': True
                    }
                    organizations_with_pdfs.append(org_info)
                    
                    if len(organizations_with_pdfs) >= limit:
                        break
            
            except Exception as e:
                logger.warning("Failed to check PDFs for organization", ein=org.ein, error=str(e))
                continue
        
        logger.info("Found organizations with PDFs", count=len(organizations_with_pdfs))
        return organizations_with_pdfs 