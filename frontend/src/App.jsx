import { useEffect, useRef, useState } from "react";

import Auth from "./pages/Auth";

import {
  getCurrentUser,
  sendChatMessage,
} from "./services/api";

import "./App.css";
import "./Auth.css";


function App() {
  // =========================================
  // AUTHENTICATION
  // =========================================

  const [user, setUser] = useState(null);

  const [checkingAuth, setCheckingAuth] = useState(true);


  // =========================================
  // CHAT STATE
  // =========================================

  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      content:
        "Hello! I'm your Research Copilot. Ask me a research question, explore a topic, or upload a paper when you're ready.",
    },
  ]);

  const [message, setMessage] = useState("");

  const [isThinking, setIsThinking] = useState(false);


  // Reference used to automatically scroll
  // to the newest message.

  const messagesEndRef = useRef(null);


  // =========================================
  // CHECK AUTHENTICATION
  // =========================================

  useEffect(() => {
    const token = localStorage.getItem(
      "access_token"
    );

    // No token means user is not logged in.

    if (!token) {
      setCheckingAuth(false);
      return;
    }


    // Verify token with FastAPI.

    getCurrentUser(token)

      .then((currentUser) => {
        setUser(currentUser);
      })

      .catch(() => {
        // Token is invalid or expired.

        localStorage.removeItem(
          "access_token"
        );
      })

      .finally(() => {
        setCheckingAuth(false);
      });

  }, []);


  // =========================================
  // AUTO SCROLL CHAT
  // =========================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isThinking]);


  // =========================================
  // LOGOUT
  // =========================================

  const handleLogout = () => {
    localStorage.removeItem(
      "access_token"
    );

    setUser(null);

    // Reset chat.

    setMessages([
      {
        id: Date.now(),
        role: "assistant",
        content:
          "Hello! I'm your Research Copilot. Ask me a research question, explore a topic, or upload a paper when you're ready.",
      },
    ]);
  };


  // =========================================
  // SEND MESSAGE TO FASTAPI
  // =========================================

  const handleSend = async (event) => {
    event?.preventDefault();


    const trimmedMessage =
      message.trim();


    // Don't send empty messages.

    if (
      !trimmedMessage ||
      isThinking
    ) {
      return;
    }


    // =======================================
    // ADD USER MESSAGE
    // =======================================

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: trimmedMessage,
    };


    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);


    // Clear input.

    setMessage("");


    // Show AI thinking animation.

    setIsThinking(true);


    try {
      // =====================================
      // GET JWT TOKEN
      // =====================================

      const token =
        localStorage.getItem(
          "access_token"
        );


      if (!token) {
        throw new Error(
          "Your session has expired. Please log in again."
        );
      }


      // =====================================
      // CALL FASTAPI /chat
      // =====================================

      const data =
        await sendChatMessage(
          trimmedMessage,
          token
        );


      // =====================================
      // ADD AI RESPONSE
      // =====================================

      setMessages((previous) => [
        ...previous,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data.answer,
        },
      ]);

    } catch (error) {

      // =====================================
      // SHOW ERROR
      // =====================================

      setMessages((previous) => [
        ...previous,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            error.message ||
            "Something went wrong while processing your question.",
        },
      ]);

    } finally {

      setIsThinking(false);

    }
  };


  // =========================================
  // QUICK SUGGESTION
  // =========================================

  const handleSuggestion = (text) => {

    setMessage(text);


    // Focus the input.

    setTimeout(() => {

      document
        .querySelector(".chat-input")
        ?.focus();

    }, 0);
  };


  // =========================================
  // AUTH LOADING SCREEN
  // =========================================

  if (checkingAuth) {

    return (
      <div className="auth-loading">

        <div className="loading-orb">
          ✦
        </div>

        <p>
          Preparing your research workspace...
        </p>

      </div>
    );
  }


  // =========================================
  // LOGIN / REGISTER
  // =========================================

  if (!user) {

    return (
      <Auth
        onLogin={setUser}
      />
    );
  }


  // =========================================
  // MAIN RESEARCH COPILOT
  // =========================================

  return (

    <div className="copilot-app">

      {/* ===================================
          BACKGROUND EFFECTS
      ==================================== */}

      <div className="ambient ambient-one"></div>

      <div className="ambient ambient-two"></div>


      {/* ===================================
          HEADER
      ==================================== */}

      <header className="copilot-header">

        <div className="brand">

          <div className="brand-mark">

            <span>
              ✦
            </span>

          </div>


          <div>

            <h1>
              Research Copilot
            </h1>

            <span>
              AI-powered research workspace
            </span>

          </div>

        </div>


        {/* Header actions */}

        <div className="header-actions">

          {/* Online status */}

          <div className="status">

            <span className="status-dot"></span>

            Online

          </div>


          {/* User / logout */}

          <button
            className="profile-button"
            onClick={handleLogout}
            title="Click to logout"
          >

            <span className="profile-avatar">

              {user.name
                .charAt(0)
                .toUpperCase()}

            </span>


            <span>
              {user.name.split(" ")[0]}
            </span>

          </button>

        </div>

      </header>


      {/* ===================================
          CHAT MAIN
      ==================================== */}

      <main className="chat-main">

        <div className="chat-container">


          {/* =================================
              CHAT TITLE
          ================================== */}

          <div className="chat-title">

            <div className="chat-ai-icon">

              ✦

            </div>


            <div>

              <h2>
                Research Assistant
              </h2>

              <p>
                Ask questions and explore ideas
              </p>

            </div>

          </div>


          {/* =================================
              MESSAGES
          ================================== */}

          <div className="messages-area">

            {messages.map((item) => (

              <div
                key={item.id}
                className={
                  `message-row ${item.role}`
                }
              >

                {/* AI avatar */}

                {item.role === "assistant" && (

                  <div className="message-avatar">

                    ✦

                  </div>

                )}


                {/* Message content */}

                <div className="message-content">

                  <div className="message-label">

                    {item.role === "assistant"
                      ? "Research Copilot"
                      : "You"}

                  </div>


                  <div className="message-bubble">

                    {item.content}

                  </div>

                </div>

              </div>

            ))}


            {/* =================================
                THINKING ANIMATION
            ================================== */}

            {isThinking && (

              <div className="message-row assistant">

                <div className="message-avatar">

                  ✦

                </div>


                <div className="message-content">

                  <div className="message-label">

                    Research Copilot

                  </div>


                  <div className="message-bubble thinking">

                    <span></span>

                    <span></span>

                    <span></span>

                  </div>

                </div>

              </div>

            )}


            {/* Auto-scroll target */}

            <div
              ref={messagesEndRef}
            ></div>

          </div>


          {/* =================================
              QUICK SUGGESTIONS
          ================================== */}

          {messages.length === 1 && (

            <div className="chat-suggestions">


              {/* RAG */}

              <button
                onClick={() =>
                  handleSuggestion(
                    "Explain Retrieval-Augmented Generation"
                  )
                }
              >

                <span>
                  ◈
                </span>

                Explain RAG

              </button>


              {/* Research paper */}

              <button
                onClick={() =>
                  handleSuggestion(
                    "How should I analyze a research paper?"
                  )
                }
              >

                <span>
                  ⌕
                </span>

                Analyze a paper

              </button>


              {/* Research ideas */}

              <button
                onClick={() =>
                  handleSuggestion(
                    "Give me research directions for AI"
                  )
                }
              >

                <span>
                  ✦
                </span>

                Find research ideas

              </button>

            </div>

          )}


          {/* =================================
              CHAT INPUT
          ================================== */}

          <form
            className="chat-input-wrapper"
            onSubmit={handleSend}
          >

            <div className="chat-input-top">


              {/* Attachment */}

              <button
                type="button"
                className="attachment-button"
                title="Document upload will be added during RAG phase"
              >

                +

              </button>


              {/* Message input */}

              <input
                className="chat-input"
                type="text"
                value={message}
                onChange={(event) =>
                  setMessage(
                    event.target.value
                  )
                }
                placeholder="Ask your research question..."
                disabled={isThinking}
              />


              {/* Send */}

              <button
                className="chat-send"
                type="submit"
                disabled={
                  !message.trim() ||
                  isThinking
                }
              >

                ↑

              </button>

            </div>


            {/* Input footer */}

            <div className="chat-input-footer">

              <span>
                ✦ AI Research Assistant
              </span>

              <span>
                Enter to send
              </span>

            </div>

          </form>

        </div>

      </main>

    </div>
  );
}


export default App;