import { useState } from "react";
import { loginUser, registerUser } from "../services/api";

function Auth({ onLogin }) {
  const [mode, setMode] = useState("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isLogin = mode === "login";

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        const data = await loginUser(email, password);

        localStorage.setItem(
          "access_token",
          data.access_token
        );

        onLogin(data.user);
      } else {
        await registerUser(name, email, password);

        setMode("login");
        setName("");
        setPassword("");

        alert("Account created successfully. Please sign in.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode(isLogin ? "register" : "login");

    setError("");
    setName("");
    setEmail("");
    setPassword("");
  };

  return (
    <div className="auth-page">

      {/* Background effects */}
      <div className="auth-glow auth-glow-one"></div>
      <div className="auth-glow auth-glow-two"></div>

      {/* Left visual section */}
      <section className="auth-showcase">

        <div className="showcase-brand">
          <div className="showcase-logo">✦</div>

          <span>Research Copilot</span>
        </div>

        <div className="showcase-content">

          <div className="floating-symbol symbol-one">
            ◈
          </div>

          <div className="floating-symbol symbol-two">
            ✧
          </div>

          <div className="floating-symbol symbol-three">
            ⌁
          </div>

          <div className="showcase-orb">
            <div className="showcase-orb-inner">
              ✦
            </div>
          </div>

          <p className="showcase-label">
            INTELLIGENT RESEARCH
          </p>

          <h1>
            Think deeper.
            <br />
            <span>Research smarter.</span>
          </h1>

          <p className="showcase-description">
            Explore papers, understand complex ideas,
            analyze documents and discover insights with
            your AI research companion.
          </p>

        </div>

        <div className="showcase-footer">
          <span>✦</span>
          AI-powered research workspace
        </div>

      </section>

      {/* Authentication section */}
      <section className="auth-panel">

        <div className="auth-container">

          <div className="mobile-brand">
            <div className="showcase-logo">✦</div>
            <span>Research Copilot</span>
          </div>

          <div className="auth-heading">

            <div className="auth-mini-icon">
              {isLogin ? "→" : "✦"}
            </div>

            <h2>
              {isLogin
                ? "Welcome back"
                : "Create your workspace"}
            </h2>

            <p>
              {isLogin
                ? "Continue your research journey."
                : "Start exploring research with AI."}
            </p>

          </div>

          <form
            className="auth-form"
            onSubmit={handleSubmit}
          >

            {!isLogin && (
              <div className="auth-field">

                <label htmlFor="name">
                  Your name
                </label>

                <input
                  id="name"
                  type="text"
                  placeholder="Enter your name"
                  value={name}
                  onChange={(event) =>
                    setName(event.target.value)
                  }
                  required
                />

              </div>
            )}

            <div className="auth-field">

              <label htmlFor="email">
                Email address
              </label>

              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                required
              />

            </div>

            <div className="auth-field">

              <div className="password-label">

                <label htmlFor="password">
                  Password
                </label>

                {isLogin && (
                  <span>
                    Secure access
                  </span>
                )}

              </div>

              <input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                required
              />

            </div>

            {error && (
              <div className="auth-error">
                <span>!</span>
                {error}
              </div>
            )}

            <button
              className="auth-submit"
              type="submit"
              disabled={loading}
            >
              <span>
                {loading
                  ? "Please wait..."
                  : isLogin
                    ? "Enter Research Copilot"
                    : "Create Account"}
              </span>

              {!loading && (
                <span className="submit-arrow">
                  →
                </span>
              )}
            </button>

          </form>

          <div className="auth-divider">
            <span></span>
            <p>or</p>
            <span></span>
          </div>

          <button
            className="auth-switch"
            onClick={switchMode}
          >
            {isLogin
              ? "New to Research Copilot?"
              : "Already have an account?"}

            <strong>
              {isLogin
                ? " Create account"
                : " Sign in"}
            </strong>
          </button>

          <p className="auth-note">
            By continuing, you agree to use Research
            Copilot responsibly for research and learning.
          </p>

        </div>

      </section>

    </div>
  );
}

export default Auth;