async function request(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const msg = (data && (data.detail || data.error)) || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  getLLM: () => request("GET", "/api/config/llm"),
  putLLM: (cfg) => request("PUT", "/api/config/llm", cfg),
  getMCP: () => request("GET", "/api/config/mcp"),
  putMCP: (servers) => request("PUT", "/api/config/mcp", { servers }),
  getMCPStatus: () => request("GET", "/api/mcp/status"),
  getHistory: () => request("GET", "/api/chat/history"),
  sendMessage: (message) =>
    request("POST", "/api/chat/message", { message }),
  clearHistory: () => request("DELETE", "/api/chat/history"),
};
