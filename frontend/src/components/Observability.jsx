import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const MASK = "***";

export default function Observability() {
  const [cfg, setCfg] = useState(null);
  const [status, setStatus] = useState(null);
  const [keyDirty, setKeyDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(null);

  useEffect(() => {
    api.getObservability().then(setCfg).catch((e) => setError(e.message));
    api.getObservabilityStatus().then(setStatus).catch(() => {});
  }, []);

  if (!cfg) return <div className="panel">Loading…</div>;

  function update(patch) {
    setCfg((prev) => ({ ...prev, ...patch }));
    setOk(null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    setOk(null);
    try {
      const payload = { ...cfg };
      if (!keyDirty) payload.secret_key = MASK;
      const result = await api.putObservability(payload);
      setCfg(result);
      setKeyDirty(false);
      const s = await api.getObservabilityStatus();
      setStatus(s);
      setOk("Saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const dashboardUrl = (cfg.host || "").replace(/\/$/, "");
  const active = status?.enabled;

  return (
    <div className="panel">
      <h2>Observability (Langfuse)</h2>
      {error && <div className="error-banner">{error}</div>}
      {ok && <div className="success-banner">{ok}</div>}

      <div className="form-row">
        <label>Status</label>
        <div>
          {active ? (
            <span style={{ color: "#2a8f3f" }}>● tracing active</span>
          ) : (
            <span style={{ color: "#888" }}>○ tracing inactive</span>
          )}
        </div>
        <div className="hint">
          Runs in docker-compose at <code>http://localhost:3000</code>. Create a
          project in the Langfuse UI, then paste the public + secret keys below.
        </div>
      </div>

      <div className="form-row">
        <label>Enabled</label>
        <input
          type="checkbox"
          checked={!!cfg.enabled}
          onChange={(e) => update({ enabled: e.target.checked })}
        />
      </div>

      <div className="form-row">
        <label>Host</label>
        <input
          type="url"
          value={cfg.host || ""}
          onChange={(e) => update({ host: e.target.value })}
          placeholder="http://localhost:3000"
        />
      </div>

      <div className="form-row">
        <label>Public Key</label>
        <input
          type="text"
          value={cfg.public_key || ""}
          onChange={(e) => update({ public_key: e.target.value })}
          placeholder="pk-lf-…"
        />
      </div>

      <div className="form-row">
        <label>Secret Key</label>
        <input
          type="password"
          value={cfg.secret_key || ""}
          onChange={(e) => {
            update({ secret_key: e.target.value });
            setKeyDirty(true);
          }}
          placeholder={cfg.secret_key === MASK ? "(key set — leave to keep)" : "sk-lf-…"}
        />
        <div className="hint">Stored in plaintext at data/observability.json.</div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
        {dashboardUrl && (
          <a
            href={dashboardUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: "0.9rem" }}
          >
            Open Langfuse dashboard ↗
          </a>
        )}
      </div>
    </div>
  );
}
