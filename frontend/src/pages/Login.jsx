import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const [loginName, setLoginName] = useState(window.localStorage.getItem('crisisiq-user') || '');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const navigate = useNavigate();

  const handleLogin = () => {
    const user = loginName.trim();
    const password = loginPassword.trim();
    if (!user || !password) {
      setLoginError('Please enter both username and password.');
      return;
    }

    setLoginError('');
    window.localStorage.setItem('crisisiq-user', user);
    window.localStorage.setItem('crisisiq-authenticated', 'true');
    // Navigate safely to the main dashboard
    navigate('/');
  };

  return (
    <div className="login-splash-page">
      <section className="login-card card soft-glow">
        <div className="login-header">
          <span className="brand-pill">CrisisIQ</span>
          <h1>Sign in</h1>
          <p>Enter your credentials to access weather risk intelligence.</p>
        </div>

        <div className="login-form">
          <label>
            Username
            <input
              value={loginName}
              onChange={(event) => setLoginName(event.target.value)}
              placeholder="Your username"
              aria-label="Username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              placeholder="Password"
              aria-label="Password"
            />
          </label>
          {loginError && <div className="alert-inline">{loginError}</div>}
          <button className="primary-btn splash-btn" onClick={handleLogin}>
            Sign in
          </button>
        </div>

        <div className="login-note">
          <p>Hint: any username/password works locally. This page separates access from the dashboard.</p>
        </div>
      </section>
    </div>
  );
}
