/**
 * SF Fog RFC — ProPublica Nonprofit Explorer MCP Server (Cloudflare Worker)
 * Native TypeScript implementation providing Model Context Protocol (MCP) JSON-RPC 2.0,
 * SSE transport, and REST API proxying ProPublica Nonprofit Explorer API v2.
 */

interface Env {
  LOG_LEVEL?: string;
  PROPUBLICA_API_BASE_URL?: string;
}

const PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2";

const TOOLS_MANIFEST = [
  {
    name: "search_nonprofits",
    description: "Search for nonprofit organizations using ProPublica's IRS database.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query (name, keyword)" },
        state: { type: "string", description: "Two-letter US state code (e.g. CA, NY)" },
        ntee_code: { type: "string", description: "NTEE category code (e.g. N60)" },
        subsection_code: { type: "string", description: "501(c) subsection (e.g. '3', '7')" },
        page: { type: "number", description: "Page number (0-indexed, default 0)" }
      },
      required: ["query"]
    }
  },
  {
    name: "get_organization",
    description: "Retrieve comprehensive details for an organization by EIN (e.g. 571147298 or 57-1147298).",
    inputSchema: {
      type: "object",
      properties: {
        ein: { type: "string", description: "Federal Employer Identification Number (EIN)" }
      },
      required: ["ein"]
    }
  },
  {
    name: "get_organization_filings",
    description: "Retrieve historical IRS 990 filings and tax extracts for an organization by EIN.",
    inputSchema: {
      type: "object",
      properties: {
        ein: { type: "string", description: "Federal EIN" }
      },
      required: ["ein"]
    }
  },
  {
    name: "analyze_nonprofit_financials",
    description: "Analyze multi-year financial trends (revenue, assets, expenses) for an organization by EIN.",
    inputSchema: {
      type: "object",
      properties: {
        ein: { type: "string", description: "Federal EIN" },
        years: { type: "number", description: "Number of years to analyze (default: 3)" }
      },
      required: ["ein"]
    }
  },
  {
    name: "search_similar_nonprofits",
    description: "Find similar peer nonprofits based on state, NTEE code, and subsection.",
    inputSchema: {
      type: "object",
      properties: {
        ein: { type: "string", description: "Target organization EIN to base similarity on" },
        limit: { type: "number", description: "Max results to return (default: 10)" }
      },
      required: ["ein"]
    }
  }
];

function cleanEin(raw: string): string {
  return String(raw).replace(/[^0-9]/g, "");
}

async function fetchFromProPublica(path: string, params?: Record<string, string | number | undefined>): Promise<any> {
  const url = new URL(`${PROPUBLICA_BASE}${path}`);
  if (params) {
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null && val !== "") {
        url.searchParams.append(key, String(val));
      }
    }
  }
  const response = await fetch(url.toString(), {
    headers: {
      "User-Agent": "SF-Fog-RFC-MCP-Worker/1.0 (president@fogrugby.com)",
      "Accept": "application/json"
    }
  });
  if (!response.ok) {
    throw new Error(`ProPublica API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function executeTool(name: string, args: Record<string, any>): Promise<any> {
  switch (name) {
    case "search_nonprofits": {
      const q = args.query;
      const params: Record<string, any> = { q };
      if (args.state) params["state[id]"] = args.state;
      if (args.ntee_code) params["ntee[id]"] = args.ntee_code;
      if (args.subsection_code) params["c_code[id]"] = args.subsection_code;
      if (args.page !== undefined) params["page"] = args.page;

      const data = await fetchFromProPublica("/search.json", params);
      return {
        total_results: data.total_results || 0,
        page: data.cur_page || 0,
        organizations: (data.organizations || []).map((org: any) => ({
          ein: org.strein || String(org.ein),
          name: org.name,
          city: org.city,
          state: org.state,
          ntee_code: org.ntee_code,
          subsection: `501(c)(${org.subseccd || "3"})`,
          have_filings: org.have_filings,
          have_pdfs: org.have_pdfs
        }))
      };
    }

    case "get_organization": {
      const ein = cleanEin(args.ein);
      const data = await fetchFromProPublica(`/organizations/${ein}.json`);
      const org = data.organization || {};
      return {
        ein: String(org.ein || ein),
        name: org.name,
        care_of: org.careofname,
        address: `${org.address || ""}, ${org.city || ""}, ${org.state || ""} ${org.zipcode || ""}`.trim(),
        ruling_date: org.ruling_date,
        subsection: `501(c)(${org.subsection_code || "3"})`,
        ntee_code: org.ntee_code,
        revenue_amount: org.revenue_amount || 0,
        asset_amount: org.asset_amount || 0,
        income_amount: org.income_amount || 0,
        filings_count: (data.filings_with_data || []).length + (data.filings_without_data || []).length,
        raw_organization: org
      };
    }

    case "get_organization_filings": {
      const ein = cleanEin(args.ein);
      const data = await fetchFromProPublica(`/organizations/${ein}.json`);
      const org = data.organization || {};
      return {
        ein: String(org.ein || ein),
        name: org.name,
        filings_with_data: data.filings_with_data || [],
        filings_without_data: data.filings_without_data || []
      };
    }

    case "analyze_nonprofit_financials": {
      const ein = cleanEin(args.ein);
      const years = Math.min(Number(args.years) || 3, 10);
      const data = await fetchFromProPublica(`/organizations/${ein}.json`);
      const org = data.organization || {};
      const filings = (data.filings_with_data || []).slice(0, years);

      const summaries = filings.map((f: any) => ({
        tax_year: f.tax_prd_yr,
        form_type: f.formtype_str || "990",
        total_revenue: f.totrevenue || f.totrev2 || 0,
        total_expenses: f.totfuncexpns || f.totexp2 || 0,
        net_income: (f.totrevenue || 0) - (f.totfuncexpns || 0),
        total_assets: f.totassetsend || 0,
        total_liabilities: f.totliabend || 0,
        net_assets: (f.totassetsend || 0) - (f.totliabend || 0)
      }));

      return {
        ein: String(org.ein || ein),
        name: org.name,
        years_analyzed: summaries.length,
        financial_summary: summaries,
        current_bmf_revenue: org.revenue_amount || 0,
        current_bmf_assets: org.asset_amount || 0
      };
    }

    case "search_similar_nonprofits": {
      const ein = cleanEin(args.ein);
      const limit = Math.min(Number(args.limit) || 10, 25);
      const target = await fetchFromProPublica(`/organizations/${ein}.json`);
      const org = target.organization || {};

      const searchParams: Record<string, any> = {
        q: org.city || "Rugby",
        "state[id]": org.state || "CA"
      };
      if (org.subsection_code) searchParams["c_code[id]"] = org.subsection_code;

      const results = await fetchFromProPublica("/search.json", searchParams);
      const peers = (results.organizations || [])
        .filter((item: any) => String(item.ein) !== String(org.ein))
        .slice(0, limit)
        .map((item: any) => ({
          ein: String(item.ein),
          name: item.name,
          city: item.city,
          state: item.state,
          ntee_code: item.ntee_code,
          subsection: `501(c)(${item.subseccd || "3"})`
        }));

      return {
        target_ein: String(org.ein || ein),
        target_name: org.name,
        state: org.state,
        similar_organizations: peers
      };
    }

    default:
      throw new Error(`Tool not found: ${name}`);
  }
}

function jsonRpcResponse(id: any, result: any): Response {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id, result }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}

function jsonRpcError(id: any, code: number, message: string): Response {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}

function getDashboardHtml(origin: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SF Fog RFC — ProPublica MCP Server</title>
  <style>
    :root {
      --fog-blue: #006EB6;
      --fog-light-blue: #24A0F1;
      --fog-dark-blue: #00243C;
      --fog-gray: #DCDDDE;
      --fog-dark-gray: #141718;
      --fog-white: #FFFFFF;
      --fog-green: #157A38;
      --fog-radius-btn: 2px;
      --fog-radius-card: 4px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Futura PT", Futura, Arial, Helvetica, sans-serif;
      background-color: var(--fog-dark-blue);
      color: var(--fog-dark-gray);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: var(--fog-dark-blue);
      border-bottom: 2px solid var(--fog-blue);
      padding: 24px 32px;
      color: var(--fog-white);
    }
    .header-content {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .logo-badge {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .logo-badge h1 {
      font-size: 20px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      font-weight: 700;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(36, 160, 241, 0.15);
      border: 1px solid var(--fog-light-blue);
      color: var(--fog-light-blue);
      padding: 4px 12px;
      font-size: 13px;
      border-radius: var(--fog-radius-btn);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #22c55e;
      border-radius: 50%;
    }
    main {
      flex: 1;
      max-width: 1200px;
      width: 100%;
      margin: 32px auto;
      padding: 0 24px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }
    @media (max-width: 840px) {
      main { grid-template-columns: 1fr; }
    }
    .card {
      background: var(--fog-white);
      border-radius: var(--fog-radius-card);
      padding: 28px;
      border: 1px solid var(--fog-gray);
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    h2 {
      font-size: 18px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--fog-blue);
      margin-bottom: 16px;
      border-bottom: 2px solid var(--fog-gray);
      padding-bottom: 8px;
    }
    p {
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 16px;
    }
    .tool-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .tool-item {
      background: #f8fafc;
      border: 1px solid var(--fog-gray);
      padding: 12px 16px;
      border-radius: var(--fog-radius-card);
    }
    .tool-name {
      font-weight: 700;
      color: var(--fog-blue);
      font-family: monospace;
      font-size: 14px;
    }
    .tool-desc {
      font-size: 13px;
      color: #4b5563;
      margin-top: 4px;
    }
    .form-group {
      margin-bottom: 16px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
      color: var(--fog-dark-blue);
    }
    input {
      width: 100%;
      padding: 10px 14px;
      border: 1px solid var(--fog-gray);
      border-radius: var(--fog-radius-btn);
      font-size: 15px;
      font-family: inherit;
    }
    input:focus {
      outline: none;
      border-color: var(--fog-blue);
      box-shadow: 0 0 0 2px rgba(0, 110, 182, 0.2);
    }
    button {
      background: var(--fog-blue);
      color: var(--fog-white);
      border: none;
      padding: 12px 24px;
      border-radius: var(--fog-radius-btn);
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    button:hover {
      background: var(--fog-light-blue);
    }
    pre {
      background: var(--fog-dark-blue);
      color: #93c5fd;
      padding: 16px;
      border-radius: var(--fog-radius-card);
      font-size: 12px;
      overflow-x: auto;
      max-height: 340px;
      margin-top: 16px;
      font-family: "SFMono-Regular", Consolas, Menlo, monospace;
    }
    footer {
      background: #001625;
      padding: 20px;
      text-align: center;
      color: var(--fog-gray);
      font-size: 13px;
      border-top: 1px solid rgba(255,255,255,0.1);
    }
  </style>
</head>
<body>
  <header>
    <div class="header-content">
      <div class="logo-badge">
        <h1>San Francisco Fog RFC — ProPublica MCP Server</h1>
      </div>
      <div class="status-badge">
        <div class="pulse-dot"></div>
        Cloudflare Edge Active
      </div>
    </div>
  </header>

  <main>
    <section class="card">
      <h2>Server Capabilities & Endpoints</h2>
      <p>This Cloudflare Worker provides a live Model Context Protocol (MCP) server proxying the ProPublica Nonprofit Explorer API with 0ms cold-start edge execution.</p>
      
      <div style="margin-bottom: 20px;">
        <label>MCP Transport Endpoint</label>
        <input type="text" readonly value="${origin}/mcp" onclick="this.select()">
      </div>

      <h3 style="font-size: 14px; text-transform: uppercase; margin-bottom: 8px; color: var(--fog-dark-blue);">Available MCP Tools</h3>
      <ul class="tool-list">
        <li class="tool-item">
          <div class="tool-name">search_nonprofits</div>
          <div class="tool-desc">Search IRS database by keywords, state, NTEE code, or 501(c) subsection.</div>
        </li>
        <li class="tool-item">
          <div class="tool-name">get_organization</div>
          <div class="tool-desc">Extract full IRS BMF master profile, ruling date, and revenue/assets by EIN.</div>
        </li>
        <li class="tool-item">
          <div class="tool-name">get_organization_filings</div>
          <div class="tool-desc">Retrieve historical annual Form 990 / 990-EZ filings and available PDF extracts.</div>
        </li>
        <li class="tool-item">
          <div class="tool-name">analyze_nonprofit_financials</div>
          <div class="tool-desc">Multi-year trend analysis of revenue, expenses, net assets, and liabilities.</div>
        </li>
        <li class="tool-item">
          <div class="tool-name">search_similar_nonprofits</div>
          <div class="tool-desc">Discover peer organizations in the same city/state with shared tax subsections.</div>
        </li>
      </ul>
    </section>

    <section class="card">
      <h2>Live Query Console</h2>
      <div class="form-group">
        <label>Search Nonprofits or Enter EIN</label>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="queryInput" value="571147298" placeholder="e.g. 571147298 or San Francisco Fog">
          <button id="searchBtn">Query</button>
        </div>
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px;">
        <button style="padding: 6px 12px; font-size: 12px; background: #64748b;" onclick="loadPreset('571147298', 'ein')">SF Fog RFC (EIN)</button>
        <button style="padding: 6px 12px; font-size: 12px; background: #64748b;" onclick="loadPreset('San Francisco Fog Rugby', 'search')">Search Name</button>
        <button style="padding: 6px 12px; font-size: 12px; background: #64748b;" onclick="loadPreset('942879185', 'ein')">Dancers Group (Sponsor)</button>
      </div>

      <div id="loading" style="display: none; padding: 12px; color: var(--fog-blue); font-weight: bold;">Querying ProPublica Nonprofit Explorer API...</div>
      <pre id="outputJson">// Results will appear here...</pre>
    </section>
  </main>

  <footer>
    San Francisco Fog Rugby Football Club Inc &copy; 2000&ndash;2026 &bull; Cloudflare Workers Edge Infrastructure
  </footer>

  <script>
    function loadPreset(val, type) {
      document.getElementById('queryInput').value = val;
      runQuery();
    }

    async function runQuery() {
      const input = document.getElementById('queryInput').value.trim();
      if (!input) return;
      
      const output = document.getElementById('outputJson');
      const loading = document.getElementById('loading');
      loading.style.display = 'block';
      output.textContent = '// Loading...';

      try {
        const isEin = /^[0-9\\-]+$/.test(input) && input.replace(/[^0-9]/g, '').length >= 9;
        const url = isEin 
          ? '/api/organizations/' + input.replace(/[^0-9]/g, '')
          : '/api/search?q=' + encodeURIComponent(input);

        const res = await fetch(url);
        const data = await res.json();
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        output.textContent = '// Error: ' + err.message;
      } finally {
        loading.style.display = 'none';
      }
    }

    document.getElementById('searchBtn').addEventListener('click', runQuery);
    document.getElementById('queryInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') runQuery();
    });
  </script>
</body>
</html>`;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const origin = url.origin;

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key"
        }
      });
    }

    // Health check
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "healthy", timestamp: new Date().toISOString() }), {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
      });
    }

    // Interactive Dashboard
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(getDashboardHtml(origin), {
        headers: { "Content-Type": "text/html; charset=utf-8" }
      });
    }

    // REST: Search
    if (url.pathname === "/api/search" && request.method === "GET") {
      try {
        const q = url.searchParams.get("q") || "";
        const state = url.searchParams.get("state") || undefined;
        const data = await executeTool("search_nonprofits", { query: q, state });
        return new Response(JSON.stringify(data), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      } catch (err: any) {
        return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json" } });
      }
    }

    // REST: Organization
    const orgMatch = url.pathname.match(/^\/api\/organizations\/([0-9\-]+)$/);
    if (orgMatch && request.method === "GET") {
      try {
        const ein = orgMatch[1];
        const data = await executeTool("get_organization", { ein });
        return new Response(JSON.stringify(data), {
          headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
        });
      } catch (err: any) {
        return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json" } });
      }
    }

    // Model Context Protocol (MCP) JSON-RPC 2.0 Handler
    if ((url.pathname === "/mcp" || url.pathname === "/") && request.method === "POST") {
      try {
        const body: any = await request.json();
        const { id, method, params } = body;

        if (method === "initialize") {
          return jsonRpcResponse(id, {
            protocolVersion: "2024-11-05",
            capabilities: {
              tools: { listChanged: false }
            },
            serverInfo: {
              name: "fog-propublica-mcp",
              version: "1.0.0"
            }
          });
        }

        if (method === "notifications/initialized") {
          return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": "*" } });
        }

        if (method === "ping") {
          return jsonRpcResponse(id, {});
        }

        if (method === "tools/list") {
          return jsonRpcResponse(id, { tools: TOOLS_MANIFEST });
        }

        if (method === "tools/call") {
          const toolName = params?.name;
          const toolArgs = params?.arguments || {};
          try {
            const toolResult = await executeTool(toolName, toolArgs);
            return jsonRpcResponse(id, {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(toolResult, null, 2)
                }
              ]
            });
          } catch (toolErr: any) {
            return jsonRpcResponse(id, {
              isError: true,
              content: [
                {
                  type: "text",
                  text: `Error executing ${toolName}: ${toolErr.message}`
                }
              ]
            });
          }
        }

        return jsonRpcError(id, -32601, `Method not found: ${method}`);
      } catch (parseErr: any) {
        return jsonRpcError(null, -32700, `Parse error: ${parseErr.message}`);
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};
