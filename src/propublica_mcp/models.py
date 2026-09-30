"""Data models for ProPublica nonprofit data."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class NonprofitOrganization(BaseModel):
    """Model for a nonprofit organization from ProPublica API."""
    
    ein: str = Field(..., description="Employer Identification Number")
    strein: Optional[str] = Field(None, description="Formatted EIN (XX-XXXXXXX)")
    name: str = Field(..., description="Organization name")
    sub_name: Optional[str] = Field(None, description="Secondary/subtitle name")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State abbreviation")
    zipcode: Optional[str] = Field(None, description="ZIP code")
    subseccd: Optional[str] = Field(None, description="501(c) subsection code")
    ntee_code: Optional[str] = Field(None, description="NTEE category code")
    guidestar_url: Optional[str] = Field(None, description="GuideStar profile URL")
    nccs_url: Optional[str] = Field(None, description="NCCS profile URL")
    updated: Optional[datetime] = Field(None, description="Last updated timestamp")
    
    @field_validator('ein')
    @classmethod
    def validate_ein(cls, v):
        """Validate EIN format."""
        if v and not re.match(r'^\d{9}$', str(v).replace('-', '')):
            raise ValueError('EIN must be 9 digits')
        return v
    
    @property
    def formatted_ein(self) -> str:
        """Return EIN in XX-XXXXXXX format."""
        if self.strein:
            return self.strein
        if self.ein and len(str(self.ein)) >= 9:
            ein_str = str(self.ein).zfill(9)
            return f"{ein_str[:2]}-{ein_str[2:]}"
        return self.ein or ""
    
    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.address, self.city, self.state, self.zipcode]
        return ", ".join(part for part in parts if part)


class Filing(BaseModel):
    """Model for a nonprofit's Form 990 filing."""
    
    ein: str = Field(..., description="Organization EIN")
    tax_year: Optional[int] = Field(None, description="Tax year")
    form_type: Optional[str] = Field(None, description="Form type (990, 990EZ, 990PF)")
    pdf_url: Optional[str] = Field(None, description="PDF document URL")
    totrevenue: Optional[float] = Field(None, description="Total revenue")
    totfuncexpns: Optional[float] = Field(None, description="Total functional expenses")
    totassetsend: Optional[float] = Field(None, description="Total assets at end of year")
    totliabend: Optional[float] = Field(None, description="Total liabilities at end of year")
    filing_date: Optional[datetime] = Field(None, description="Date filed")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Complete form data")
    
    @property
    def net_assets(self) -> Optional[float]:
        """Calculate net assets (assets - liabilities)."""
        if self.totassetsend is not None and self.totliabend is not None:
            return self.totassetsend - self.totliabend
        return None
    
    @property
    def expense_ratio(self) -> Optional[float]:
        """Calculate expense ratio (expenses / revenue)."""
        if self.totfuncexpns is not None and self.totrevenue is not None and self.totrevenue > 0:
            return self.totfuncexpns / self.totrevenue
        return None


class SearchResult(BaseModel):
    """Model for search results from ProPublica API."""
    
    total_results: int = Field(..., description="Total number of matching organizations")
    num_pages: int = Field(..., description="Number of pages in result set")
    cur_page: int = Field(..., description="Current page (zero-indexed)")
    per_page: int = Field(..., description="Results per page")
    page_offset: int = Field(..., description="Number of results on previous pages")
    search_query: Optional[str] = Field(None, description="Search query used")
    selected_state: Optional[str] = Field(None, description="State filter applied")
    selected_ntee: Optional[str] = Field(None, description="NTEE filter applied")
    selected_c_code: Optional[str] = Field(None, description="501(c) code filter applied")
    organizations: List[NonprofitOrganization] = Field(default_factory=list, description="List of organizations")


class FinancialSummary(BaseModel):
    """Model for multi-year financial analysis."""
    
    ein: str = Field(..., description="Organization EIN")
    organization_name: str = Field(..., description="Organization name")
    year_range_start: int = Field(..., description="Analysis start year")
    year_range_end: int = Field(..., description="Analysis end year")
    filings_analyzed: int = Field(..., description="Number of filings included")
    
    # Revenue metrics
    avg_revenue: Optional[float] = Field(None, description="Average annual revenue")
    revenue_growth_rate: Optional[float] = Field(None, description="Annual revenue growth rate")
    revenue_trend: Optional[str] = Field(None, description="Revenue trend (increasing/decreasing/stable)")
    
    # Expense metrics
    avg_expenses: Optional[float] = Field(None, description="Average annual expenses")
    avg_expense_ratio: Optional[float] = Field(None, description="Average expense ratio")
    expense_trend: Optional[str] = Field(None, description="Expense trend")
    
    # Asset metrics
    avg_net_assets: Optional[float] = Field(None, description="Average net assets")
    net_asset_growth_rate: Optional[float] = Field(None, description="Net asset growth rate")
    asset_trend: Optional[str] = Field(None, description="Asset trend")
    
    # Year-by-year data
    annual_data: List[Dict[str, Any]] = Field(default_factory=list, description="Annual financial data")


class CRMExport(BaseModel):
    """Model for CRM-ready export data."""
    
    export_id: str = Field(..., description="Unique export identifier")
    ein: str = Field(..., description="Organization EIN")
    export_format: str = Field(..., description="Export format (salesforce, hubspot, etc.)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Export timestamp")
    
    # Core organization data
    organization_data: Dict[str, Any] = Field(..., description="Organization information")
    
    # Financial summary
    financial_data: Optional[Dict[str, Any]] = Field(None, description="Financial summary data")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional export metadata")


class APIError(BaseModel):
    """Model for API error responses."""
    
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# Constants for validation and reference

NTEE_CATEGORIES = {
    1: "Arts, Culture & Humanities",
    2: "Education", 
    3: "Environment and Animals",
    4: "Health",
    5: "Human Services",
    6: "International, Foreign Affairs",
    7: "Public, Societal Benefit",
    8: "Religion Related",
    9: "Mutual/Membership Benefit",
    10: "Unknown, Unclassified"
}

SUBSECTION_CODES = {
    2: "501(c)(2)",
    3: "501(c)(3)",
    4: "501(c)(4)",
    5: "501(c)(5)",
    6: "501(c)(6)",
    7: "501(c)(7)",
    8: "501(c)(8)",
    9: "501(c)(9)",
    10: "501(c)(10)",
    11: "501(c)(11)",
    12: "501(c)(12)",
    13: "501(c)(13)",
    14: "501(c)(14)",
    15: "501(c)(15)",
    16: "501(c)(16)",
    17: "501(c)(17)",
    18: "501(c)(18)",
    19: "501(c)(19)",
    21: "501(c)(21)",
    22: "501(c)(22)",
    23: "501(c)(23)",
    25: "501(c)(25)",
    26: "501(c)(26)",
    27: "501(c)(27)",
    28: "501(c)(28)",
    92: "4947(a)(1)"
}

FORM_TYPES = ["990", "990EZ", "990PF", "990T"]

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "ZZ"  # ZZ for entities outside US
] 