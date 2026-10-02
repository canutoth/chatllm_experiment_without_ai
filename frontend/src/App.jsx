const { useEffect, useMemo, useRef, useState, useCallback } = React;

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("access_token"));
  const [userEmail, setUserEmail] = useState(localStorage.getItem("user_email") || "");
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const messagesRef = useRef(null);
  const abortControllerRef = useRef(null);

  const chatHistory = useMemo(
    () => messages.filter((msg) => msg.role === "user" || msg.role === "assistant"),
    [messages]
  );

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Load sessions and set up initial state
  const loadSessions = useCallback(async () => {
    try {
      const sessionList = await listSessions();
      setSessions(sessionList);
      if (sessionList.length > 0) {
        const sid = sessionList[0].id;
        setActiveSessionId(sid);
        const msgs = await getSessionMessages(sid);
        if (msgs.length > 0) {
          setMessages(
            msgs.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
            }))
          );
        } else {
          setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
        }
      } else {
        const newSession = await createSession();
        setSessions([newSession]);
        setActiveSessionId(newSession.id);
        setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
      }
    } catch {
      try {
        const newSession = await createSession();
        setSessions([newSession]);
        setActiveSessionId(newSession.id);
        setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
      } catch {}
    }
  }, []);

  useEffect(() => {
    if (token) {
      loadSessions();
    }
  }, [token, loadSessions]);

  const selectSession = useCallback(async (sessionId) => {
    setActiveSessionId(sessionId);
    try {
      const msgs = await getSessionMessages(sessionId);
      if (msgs.length === 0) {
        setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
      } else {
        setMessages(msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })));
      }
    } catch {
      setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
    }
  }, []);

  const onAuthSuccess = async (newToken, email) => {
    setToken(newToken);
    setUserEmail(email);
  };

  const refreshSessions = useCallback(async () => {
    try {
      const sessionList = await listSessions();
      setSessions(sessionList);
    } catch {}
  }, []);

  const handleNewSession = async () => {
    try {
      const newSession = await createSession();
      setSessions((prev) => [newSession, ...prev]);
      selectSession(newSession.id);
      setSidebarOpen(true);
    } catch (err) {
      setError("Erro ao criar sessao");
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await deleteSession(sessionId);
      const newList = sessions.filter((s) => s.id !== sessionId);
      setSessions(newList);
      if (activeSessionId === sessionId) {
        if (newList.length > 0) {
          selectSession(newList[0].id);
        } else {
          handleNewSession();
        }
      }
    } catch (err) {
      setError("Erro ao excluir sessao");
    }
  };

  const handleSelectSession = async (sessionId) => {
    if (sessionId === activeSessionId) return;
    selectSession(sessionId);
  };

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {}
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_email");
    setToken(null);
    setUserEmail("");
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
    setError("");
    setInstructionsOpen(false);
  };

  const closeInstructions = useCallback(() => setInstructionsOpen(false), []);

  const onStop = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setBusy(false);
  };

  const onSubmit = async (event, inputRef) => {
    event.preventDefault();
    const cleaned = text.trim();
    if (!cleaned || busy) return;

    setError("");
    const userMessage = { id: createMessageId(), role: "user", content: cleaned };
    const assistantMessageId = createMessageId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);
    setText("");
    setBusy(true);
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const result = await sendMessageStream({
        message: cleaned,
        history: chatHistory,
        session_id: activeSessionId,
        signal: abortController.signal,
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: `${msg.content}${delta}` }
                : msg
            )
          );
        },
      });

      // Update session ID and title from the response
      if (result && result.session_id) {
        setActiveSessionId(result.session_id);
        if (result.title) {
          setSessions((prev) =>
            prev.map((s) =>
              s.id === result.session_id ? { ...s, title: result.title } : s
            )
          );
        }
      }
      // Refresh sessions from server to stay in sync
      refreshSessions();
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId && !msg.content.trim()
            ? { ...msg, content: "Nao foi possivel obter resposta do modelo agora." }
            : msg
        )
      );
    } catch (err) {
      const aborted = err?.name === "AbortError";
      if (!aborted) {
        setError(err.message || "Falha inesperada ao gerar resposta.");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: msg.content.trim() ? msg.content : "Nao foi possivel obter resposta do modelo agora." }
              : msg
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId && !msg.content.trim()
              ? { ...msg, content: "Resposta interrompida." }
              : msg
          )
        );
      }
    } finally {
      // Always refresh sessions to pick up auto-title even if stream was incomplete
      refreshSessions();
      abortControllerRef.current = null;
      setBusy(false);
    }
  };

  if (!token) {
    return <Auth onAuthSuccess={onAuthSuccess} />;
  }

  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      <main className="app-shell">
        <header className="app-header">
          <div className="header-left">
            <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="3" y1="4" x2="15" y2="4" />
                <line x1="3" y1="9" x2="15" y2="9" />
                <line x1="3" y1="14" x2="15" y2="14" />
              </svg>
            </button>
            <div className="brand">ChatLLM Lab</div>
          </div>
          <div className="header-right">
            <button className="header-btn" onClick={() => setInstructionsOpen(true)}>Instrucoes</button>
            <span className="user-email">{userEmail}</span>
            <button className="logout-btn" onClick={handleLogout}>Sair</button>
          </div>
        </header>

        <section className="messages" aria-live="polite" ref={messagesRef}>
          <div className="messages-inner">
            {messages.map((msg) => (
              <article key={msg.id} className={`bubble ${msg.role}`}>
                <MessageContent content={msg.content} />
              </article>
            ))}
          </div>
        </section>

        <Composer
          text={text}
          busy={busy}
          error={error}
          onChangeText={setText}
          onSubmit={onSubmit}
          onStop={onStop}
        />
      </main>

      <InstructionsModal open={instructionsOpen} onClose={closeInstructions} />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);