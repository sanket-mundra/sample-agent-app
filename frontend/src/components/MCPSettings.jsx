import React, { useEffect, useState } from "react";
import { api } from "../api.js";

function emptyServer() {
  return {
    id: `srv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    name: "",
    transport: "stdio",
    enabled: true,
    command: "",
    args: [],
    env: {},
    cwd: null,
    url: "",
    headers: {},
  };
}

function KeyValueEditor({ label, value, onChange, hint }) {
  const entries = Object.entries(value || {});
  const set = (i, key, val) => {
    const next = [...entries];
    next[i] = [key, val];
    onChange(Object.fromEntries(next.filter(([k]) => k)));
  };
  const add = () => onChange({ ...value, "": "" });
  const remove = (i) => {
    const next = entries.filter((_, idx) => idx !== i);
    onChange(Object.fromEntries(next));
  };
  return (
    <div className="form-row">
      <label>{label}</label>
      {hint && <div className="hint">{hint}</div>}
      {entries.map(([k, v], i) => (
        <div key={i} style={{ display: "flex", gap: "0.25rem", marginBottom: "0.25rem" }}>
          <input type="text" placeholder="key" value={k} onChange={(e) => set(i, e.target.value, v)} />
          <input type="text" placeholder="value" value={v} onChange={(e) => set(i, k, e.target.value)} />
          <button type="button" className="secondary" onClick={() => remove(i)}>×</button>
        </div>
      ))}
      <button type="button" className="secondary" onClick={add} style={{ alignSelf: "flex-start" }}>
        + Add
      </button>
    </div>
  );
}

function ServerForm({ server, onChange }) {
  const patch = (p) => onChange({ ...server, ...p });
  return (
    <div className="server-editor">
      <div className="form-row">
        <label>Server name</label>
        <input
          type="text"
          placeholder="e.g. filesystem"
          value={server.name}
          onChange={(e) => patch({ name: e.target.value })}
        />
      </div>

      <div className="form-row">
        <label>
          <input
            type="checkbox"
            checked={server.enabled}
            onChange={(e) => patch({ enabled: e.target.checked })}
          />{" "}
          Enabled
        </label>
      </div>

      <div className="form-row">
        <label>Transport</label>
        <select value={server.transport} onChange={(e) => patch({ transport: e.target.value })}>
          <option value="stdio">stdio</option>
          <option value="streamable_http">streamable_http</option>
          <option value="sse">sse</option>
        </select>
      </div>

      {server.transport === "stdio" ? (
        <>
          <div className="form-row">
            <label>Command</label>
            <input
              type="text"
              value={server.command || ""}
              onChange={(e) => patch({ command: e.target.value })}
              placeholder="npx"
            />
          </div>
          <div className="form-row">
            <label>Args (one per line)</label>
            <textarea
              value={(server.args || []).join("\n")}
              onChange={(e) => patch({ args: e.target.value.split("\n").filter((x) => x !== "") })}
              rows={3}
            />
          </div>
          <KeyValueEditor
            label="Environment variables"
            value={server.env}
            onChange={(env) => patch({ env })}
            hint="Values shown as *** after save — overwrite to change."
          />
          <div className="form-row">
            <label>Working directory (optional)</label>
            <input
              type="text"
              value={server.cwd || ""}
              onChange={(e) => patch({ cwd: e.target.value || null })}
            />
          </div>
        </>
      ) : (
        <>
          <div className="form-row">
            <label>URL</label>
            <input
              type="url"
              value={server.url || ""}
              onChange={(e) => patch({ url: e.target.value })}
              placeholder="https://example.com/mcp"
            />
          </div>
          <KeyValueEditor
            label="Headers"
            value={server.headers}
            onChange={(headers) => patch({ headers })}
            hint="Values shown as *** after save — overwrite to change."
          />
        </>
      )}
    </div>
  );
}

function StatusBadge({ server, status }) {
  if (!server.enabled) return <span className="status-badge disabled">disabled</span>;
  if (!status) return <span className="status-badge disabled">unsaved</span>;
  if (status.connected)
    return (
      <span className="status-badge connected">
        connected · {status.tool_count} tools
      </span>
    );
  return (
    <span className="status-badge error" title={status.error || ""}>
      disconnected
    </span>
  );
}

function ServerRow({ server, status, disabled, onEdit, onToggleEnabled, onDelete }) {
  const stop = (e) => e.stopPropagation();
  const transportLabel =
    server.transport === "stdio"
      ? server.command || "stdio"
      : server.url || server.transport;
  return (
    <div
      className={`server-row-collapsed ${disabled ? "is-disabled" : ""}`}
      onClick={disabled ? undefined : onEdit}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onEdit();
        }
      }}
    >
      <label className="row-toggle" onClick={stop}>
        <input
          type="checkbox"
          checked={server.enabled}
          onChange={onToggleEnabled}
          disabled={disabled}
        />
      </label>
      <div className="row-main">
        <div className="row-name">{server.name || <em>Unnamed server</em>}</div>
        <div className="row-sub">
          <span className="row-transport">{server.transport}</span>
          <span className="row-sep">·</span>
          <span className="row-target" title={transportLabel}>{transportLabel}</span>
        </div>
      </div>
      <StatusBadge server={server} status={status} />
      <button
        className="icon-btn danger"
        onClick={(e) => {
          stop(e);
          onDelete();
        }}
        disabled={disabled}
        title="Delete server"
        aria-label="Delete server"
      >
        ×
      </button>
    </div>
  );
}

export default function MCPSettings() {
  const [servers, setServers] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(null);
  const [editingId, setEditingId] = useState(null); // id of server being edited, or "new"
  const [draft, setDraft] = useState(null);

  async function refresh() {
    try {
      const [list, status] = await Promise.all([api.getMCP(), api.getMCPStatus()]);
      setServers(list);
      setStatuses(status);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function statusFor(id) {
    return statuses.find((s) => s.id === id);
  }

  function beginAdd() {
    setDraft(emptyServer());
    setEditingId("new");
    setOk(null);
    setError(null);
  }

  function beginEdit(server) {
    setDraft({ ...server });
    setEditingId(server.id);
    setOk(null);
    setError(null);
  }

  function cancelEdit() {
    setDraft(null);
    setEditingId(null);
    setError(null);
  }

  async function persist(nextServers, successMsg) {
    setSaving(true);
    setError(null);
    setOk(null);
    try {
      const saved = await api.putMCP(nextServers);
      setServers(saved);
      const status = await api.getMCPStatus();
      setStatuses(status);
      setOk(successMsg);
      return saved;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function saveDraft() {
    if (!draft.name.trim()) {
      setError("Server name is required.");
      return;
    }
    const exists = servers.some((s) => s.id === draft.id);
    const next = exists
      ? servers.map((s) => (s.id === draft.id ? draft : s))
      : [...servers, draft];
    const saved = await persist(next, exists ? "Server updated." : "Server added.");
    if (saved) {
      setDraft(null);
      setEditingId(null);
    }
  }

  async function deleteServer(server) {
    if (!window.confirm(`Delete server "${server.name || "unnamed"}"?`)) return;
    const next = servers.filter((s) => s.id !== server.id);
    await persist(next, "Server deleted.");
  }

  async function toggleEnabled(server) {
    const next = servers.map((s) =>
      s.id === server.id ? { ...s, enabled: !s.enabled } : s
    );
    const newEnabled = !server.enabled;
    await persist(next, newEnabled ? "Server enabled." : "Server disabled.");
  }

  const isEditing = editingId !== null;

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>MCP Servers</h2>
        <div className="button-row">
          <button className="secondary" onClick={refresh} disabled={saving}>
            Refresh status
          </button>
          <button className="secondary" onClick={beginAdd} disabled={isEditing || saving}>
            + Add server
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {ok && <div className="success-banner">{ok}</div>}

      {servers.length === 0 && editingId !== "new" && (
        <div className="empty-state">
          No MCP servers configured. Click "Add server" to get started.
        </div>
      )}

      <div className="server-list">
        {servers.map((s) => {
          if (editingId === s.id && draft) {
            return (
              <div key={s.id} className="server-row editing">
                <div className="editor-header">
                  <span className="editor-title">Edit server</span>
                  <StatusBadge server={draft} status={statusFor(s.id)} />
                </div>
                <ServerForm server={draft} onChange={setDraft} />
                <div className="editor-actions">
                  <button className="secondary" onClick={cancelEdit} disabled={saving}>
                    Cancel
                  </button>
                  <button className="primary" onClick={saveDraft} disabled={saving}>
                    {saving ? "Saving…" : "Save"}
                  </button>
                </div>
                {statusFor(s.id) && statusFor(s.id).error && (
                  <div className="error-banner" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
                    {statusFor(s.id).error}
                  </div>
                )}
              </div>
            );
          }
          return (
            <ServerRow
              key={s.id}
              server={s}
              status={statusFor(s.id)}
              disabled={isEditing}
              onEdit={() => beginEdit(s)}
              onToggleEnabled={() => toggleEnabled(s)}
              onDelete={() => deleteServer(s)}
            />
          );
        })}

        {editingId === "new" && draft && (
          <div className="server-row editing">
            <div className="editor-header">
              <span className="editor-title">New server</span>
            </div>
            <ServerForm server={draft} onChange={setDraft} />
            <div className="editor-actions">
              <button className="secondary" onClick={cancelEdit} disabled={saving}>
                Cancel
              </button>
              <button className="primary" onClick={saveDraft} disabled={saving}>
                {saving ? "Saving…" : "Add server"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
