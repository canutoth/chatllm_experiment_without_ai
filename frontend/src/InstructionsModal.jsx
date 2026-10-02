const { useEffect, useState } = React;

const INSTRUCTIONS_MAX_LENGTH = 4000;

function InstructionsModal({ open, onClose }) {
  const [content, setContent] = useState("");
  const [defaultContent, setDefaultContent] = useState("");
  const [isDefault, setIsDefault] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  const applyResult = (data) => {
    setContent(data.content);
    setDefaultContent(data.default_content);
    setIsDefault(data.is_default);
  };

  useEffect(() => {
    if (!open) return;
    setError("");
    setStatus("");
    setLoading(true);
    getInstructions()
      .then(applyResult)
      .catch((err) => setError(err.message || "Erro ao carregar instrucoes"))
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const runAction = async (action, successMessage) => {
    setError("");
    setStatus("");
    setSaving(true);
    try {
      applyResult(await action());
      setStatus(successMessage);
    } catch (err) {
      setError(err.message || "Erro ao salvar instrucoes");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = (event) => {
    event.preventDefault();
    runAction(() => saveInstructions(content), "Instrucoes salvas.");
  };

  const handleReset = () => {
    runAction(resetInstructions, "Instrucoes padrao restauradas.");
  };

  const busy = loading || saving;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form className="modal" onSubmit={handleSave} role="dialog" aria-modal="true" aria-labelledby="instructions-title">
        <h2 id="instructions-title" className="modal-title">Instrucoes personalizadas</h2>
        <p className="modal-subtitle">
          Como o ChatLLM deve responder? Estas instrucoes sao enviadas ao modelo em todas as suas conversas.
          {isDefault && !loading && <span className="modal-badge">Usando o padrao</span>}
        </p>

        <textarea
          className="modal-textarea"
          value={content}
          onChange={(e) => { setContent(e.target.value); setStatus(""); }}
          maxLength={INSTRUCTIONS_MAX_LENGTH}
          disabled={busy}
          placeholder={defaultContent}
          autoFocus
        />
        <div className="modal-meta">
          <span>{content.length}/{INSTRUCTIONS_MAX_LENGTH}</span>
          {status && <span className="modal-status">{status}</span>}
          {error && <span className="error">{error}</span>}
        </div>

        <div className="modal-actions">
          <button type="button" className="modal-btn ghost" onClick={handleReset} disabled={busy || isDefault}>
            Restaurar padrao
          </button>
          <div className="modal-actions-right">
            <button type="button" className="modal-btn" onClick={onClose}>Fechar</button>
            <button type="submit" className="modal-btn primary" disabled={busy}>
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
