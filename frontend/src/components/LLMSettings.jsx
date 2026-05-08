import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const MASK = "***";

export default function LLMSettings() {
  const [cfg, setCfg] = useState(null);
  const [keyDirty, setKeyDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(null);

  useEffect(() => {
    api.getLLM().then(setCfg).catch((e) => setError(e.message));
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
      // If user hasn't modified the key, send MASK so backend preserves existing.
      if (!keyDirty) payload.api_key = MASK;
      const result = await api.putLLM(payload);
      setCfg(result);
      setKeyDirty(false);
      setOk("Saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel">
      <h2>LLM Configuration</h2>
      {error && <div className="error-banner">{error}</div>}
      {ok && <div className="success-banner">{ok}</div>}

      <div className="form-row">
        <label>Vendor</label>
        <select value={cfg.vendor} onChange={(e) => update({ vendor: e.target.value })}>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
        </select>
      </div>

      <div className="form-row">
        <label>Model</label>
        <input
          type="text"
          value={cfg.model}
          onChange={(e) => update({ model: e.target.value })}
          placeholder={cfg.vendor === "openai" ? "gpt-4o-mini" : "claude-sonnet-4-5"}
        />
      </div>

      <div className="form-row">
        <label>API Key</label>
        <input
          type="password"
          value={cfg.api_key || ""}
          onChange={(e) => { update({ api_key: e.target.value }); setKeyDirty(true); }}
          placeholder={cfg.api_key === MASK ? "(key set — leave to keep)" : "sk-…"}
        />
        <div className="hint">Stored in plaintext at data/llm_config.json.</div>
      </div>

      <div className="form-row">
        <label>Temperature</label>
        <input
          type="number"
          min="0" max="2" step="0.1"
          value={cfg.temperature}
          onChange={(e) => update({ temperature: parseFloat(e.target.value) })}
        />
      </div>

      {cfg.vendor === "openai" && (
        <div className="form-row">
          <label>Base URL (optional)</label>
          <input
            type="url"
            value={cfg.base_url || ""}
            onChange={(e) => update({ base_url: e.target.value || null })}
            placeholder="https://api.openai.com/v1"
          />
          <div className="hint">Use for OpenAI-compatible endpoints (e.g. Ollama, vLLM).</div>
        </div>
      )}

      <div className="form-row">
        <label>System Prompt</label>
        <textarea
          value={cfg.system_prompt}
          onChange={(e) => update({ system_prompt: e.target.value })}
          rows={6}
        />
      </div>

      <button className="primary" onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  );
}
