import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const suggestions = [
  'Is Chennai at risk of cyclone today?',
  'Any disaster alerts near Mumbai?',
  'Is Delhi safe from storms?',
  'Flood risk in Kolkata?',
  'Weather risk in New York?'
];

const moodMap = {
  HIGH: { label: 'Danger', emoji: '🚨', description: 'High risk conditions detected.' },
  MEDIUM: { label: 'Caution', emoji: '⚠️', description: 'Stay alert and prepare.' },
  LOW: { label: 'Safe', emoji: '✅', description: 'Low risk, stay informed.' },
  UNKNOWN: { label: 'Unknown', emoji: '💡', description: 'Need more data to decide.' }
};

const formatNumber = (value) => (value === null || value === undefined ? 'N/A' : value);

export default function Dashboard() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [cities, setCities] = useState([]);
  const [profileUser, setProfileUser] = useState(window.localStorage.getItem('crisisiq-user') || '');
  const [profileName, setProfileName] = useState(window.localStorage.getItem('crisisiq-user') || '');
  const [compareInput, setCompareInput] = useState('');
  const [compareResults, setCompareResults] = useState([]);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    // Protected route check
    if (!window.localStorage.getItem('crisisiq-authenticated')) {
      navigate('/login');
      return;
    }

    const storedHistory = window.localStorage.getItem('crisisiq-history');
    const storedFavorites = window.localStorage.getItem('crisisiq-favorites');
    const cachedReport = window.localStorage.getItem('crisisiq-last-report');

    if (storedHistory) {
      setHistory(JSON.parse(storedHistory));
    }
    if (storedFavorites) {
      setFavorites(JSON.parse(storedFavorites));
    }
    if (!offline && profileUser) {
      loadProfile(profileUser);
    }
    if (cachedReport) {
      setReport(JSON.parse(cachedReport));
    }

    fetchCities();

    const handleOnline = () => {
      setOffline(false);
      setStatusMessage('Online. Background sync enabled.');
    };
    const handleOffline = () => {
      setOffline(true);
      setStatusMessage('Offline mode active. Using cached data.');
    };
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [navigate]);

  useEffect(() => {
    window.localStorage.setItem('crisisiq-favorites', JSON.stringify(favorites));
    if (profileUser && !offline) {
      saveProfile(profileUser, { favorites, history });
    }
  }, [favorites]);

  useEffect(() => {
    window.localStorage.setItem('crisisiq-history', JSON.stringify(history));
    if (profileUser && !offline) {
      saveProfile(profileUser, { favorites, history });
    }
  }, [history]);

  useEffect(() => {
    if (!query || !report || offline) {
      return;
    }
    const interval = setInterval(() => {
      setStatusMessage('Refreshing latest risk data...');
      analyze(query, { skipHistory: true });
    }, 300000);
    return () => clearInterval(interval);
  }, [query, report, offline]);

  const fetchCities = async () => {
    try {
      const response = await fetch('/api/cities');
      const data = await response.json();
      if (response.ok && Array.isArray(data.cities)) {
        setCities(data.cities);
      }
    } catch (err) {
      console.warn('Could not load city list.', err);
    }
  };

  const loadProfile = async (user) => {
    if (!user) return;
    try {
      const response = await fetch(`/api/profile?user=${encodeURIComponent(user)}`);
      const data = await response.json();
      if (response.ok) {
        setFavorites(data.favorites || []);
        setHistory(data.history || []);
        setStatusMessage(`Profile loaded for ${user}.`);
      }
    } catch (err) {
      console.warn('Unable to load profile.', err);
    }
  };

  const saveProfile = async (user, payload) => {
    if (!user) return;
    try {
      await fetch(`/api/profile?user=${encodeURIComponent(user)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      console.warn('Unable to save profile.', err);
    }
  };

  const handleProfileSave = async () => {
    const user = profileName.trim();
    if (!user) {
      setError('Please enter a username to sync your profile.');
      return;
    }
    window.localStorage.setItem('crisisiq-user', user);
    setProfileUser(user);
    setStatusMessage(`Syncing profile as ${user}...`);
    await loadProfile(user);
  };

  const handleLogout = () => {
    window.localStorage.removeItem('crisisiq-authenticated');
    navigate('/login');
  };

  const analyze = async (overrideQuery, options = {}) => {
    const queryText = (overrideQuery || query).trim();
    if (!queryText) {
      setError('Please enter a query.');
      return;
    }

    setError('');
    setLoading(true);
    setReport(null);

    try {
      const response = await fetch(`/api/analyze?q=${encodeURIComponent(queryText)}`);
      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || data.error || 'Unable to analyze query.');
      } else {
        setReport(data);
        window.localStorage.setItem('crisisiq-last-report', JSON.stringify(data));
        setHistory((current) => {
          if (options.skipHistory) return current;
          const filtered = current.filter((entry) => entry.location !== data.location);
          return [{
            location: data.location,
            risk_level: data.risk_level,
            risk_score: data.risk_score,
            timestamp: new Date().toISOString(),
          },
          ...filtered].slice(0, 7);
        });
        setQuery(queryText);
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
      if (!offline) {
        setOffline(true);
        setStatusMessage('Offline mode active. Using cached data.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = (text) => {
    setQuery(text);
    analyze(text);
  };

  const filteredCitySuggestions = useMemo(() => {
    const search = query.trim().toLowerCase();
    if (!search) return [];
    return cities.filter((city) => city.toLowerCase().includes(search)).slice(0, 6);
  }, [cities, query]);

  const toggleFavorite = () => {
    if (!report) return;
    const currentSaved = favorites.includes(report.location);
    setFavorites((current) => {
      if (currentSaved) {
        return current.filter((item) => item !== report.location);
      }
      return [report.location, ...current].slice(0, 8);
    });
  };

  const clearHistory = () => {
    setHistory([]);
    if (profileUser && !offline) {
      saveProfile(profileUser, { favorites, history: [] });
    }
  };

  const handleCopy = async () => {
    if (!report) return;
    await navigator.clipboard.writeText(report.text_report || '');
    setStatusMessage('Report copied to clipboard!');
    setTimeout(() => setStatusMessage(''), 1800);
  };

  const compareRisk = async (overrideInput) => {
    const isString = typeof overrideInput === 'string';
    const currentInput = (isString ? overrideInput : compareInput).trim();
    const cityList = currentInput
      .split(',')
      .map((city) => city.trim())
      .filter((city) => city.length > 0);

    if (cityList.length < 2) {
      setError('Please enter two or more cities separated by commas.');
      return;
    }

    setError('');
    setCompareLoading(true);
    setCompareResults([]);

    try {
      const response = await fetch(`/api/compare?cities=${encodeURIComponent(cityList.join(','))}`);
      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || data.error || 'Unable to compare cities.');
      } else {
        setCompareResults(data.reports || []);
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
    } finally {
      setCompareLoading(false);
    }
  };

  const compareFavorites = () => {
    if (favorites.length < 2) {
      setError('Add at least two favorites to compare.');
      return;
    }
    const favoriteCities = favorites.join(', ');
    setCompareInput(favoriteCities);
    compareRisk(favoriteCities);
  };

  const riskMood = report ? moodMap[report.risk_level] || moodMap.UNKNOWN : moodMap.UNKNOWN;
  const hasCoordinates = report?.coordinates?.latitude != null && report?.coordinates?.longitude != null;
  let mapFrameUrl = null;

  if (hasCoordinates) {
    const lat = report.coordinates.latitude;
    const lon = report.coordinates.longitude;
    const delta = 0.8;
    const minLat = lat - delta;
    const maxLat = lat + delta;
    const minLon = lon - delta;
    const maxLon = lon + delta;

    mapFrameUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${minLon}%2C${minLat}%2C${maxLon}%2C${maxLat}&layer=mapnik&marker=${lat}%2C${lon}`;
  }

  const trendItems = history.slice(0, 5);

  return (
    <div className="dashboard">
      <div className="topbar">
        <div>
          <span className="brand-pill">CrisisIQ</span>
          <h1>Disaster Radar</h1>
          <p className="hero-copy">A dashboard for weather risk, news alerts, and safety guidance.</p>
        </div>
        <div>
          <button className="ghost-btn" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </div>

      <section className="search-panel card soft-glow">
        <div className="search-header">
          <div>
            <p className="section-label">Ask anything</p>
            <h2>Find the latest risk signal</h2>
          </div>
          <button className="save-btn" onClick={toggleFavorite} disabled={!report}>
            {favorites.includes(report?.location) ? '★ Saved' : '☆ Save city'}
          </button>
        </div>

        <div className="input-row">
          <div className="input-with-autocomplete">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && analyze()}
              placeholder="e.g. Is Mumbai at risk of flooding today?"
              aria-label="Disaster query"
              autoComplete="off"
            />
            {filteredCitySuggestions.length > 0 && (
              <div className="autocomplete-list">
                {filteredCitySuggestions.map((item) => (
                  <button key={item} className="autocomplete-item" onClick={() => handleSuggestion(item)}>
                    {item}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button className="primary-btn" onClick={() => analyze()} disabled={loading}>
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>

        <div className="suggestions-row">
          {suggestions.map((item) => (
            <button key={item} className="chip" onClick={() => handleSuggestion(item)}>
              {item}
            </button>
          ))}
        </div>
      </section>

      <div className="grid-layout">
        <section className="status-card card soft-glow">
          <div className="risk-meter">
            <div className="meter-ring" style={{ '--score': report?.risk_score ?? 0 }}>
              <div className="meter-center">
                <span>{riskMood.emoji}</span>
                <strong>{report?.risk_score ?? '--'}</strong>
                <small>Risk score</small>
              </div>
            </div>
          </div>
          <div className="status-details">
            <p className="section-label">Current mood</p>
            <h3>{riskMood.label}</h3>
            <p>{riskMood.description}</p>
            <div className="pill-row">
              <span>{report?.location || 'No location'}</span>
              <span>{report?.weather?.condition || 'No condition'}</span>
            </div>
          </div>
        </section>

        <section className="insights-card card soft-glow">
          <div className="insight-item">
            <p className="small-label">Weather</p>
            <strong>{formatNumber(report?.weather?.temperature_c)}°C</strong>
            <span>{formatNumber(report?.weather?.humidity_percent)}% humidity</span>
          </div>
          <div className="insight-item">
            <p className="small-label">Wind</p>
            <strong>{formatNumber(report?.weather?.wind_speed_ms)} m/s</strong>
            <span>{formatNumber(report?.weather?.wind_gust_ms)} m/s gust</span>
          </div>
          <div className="insight-item">
            <p className="small-label">Alerts</p>
            <strong>{report?.news_alerts?.length ?? 0}</strong>
            <span>Recent disaster headlines</span>
          </div>
          <div className="insight-item">
            <p className="small-label">Categories</p>
            <strong>{(report?.event_categories || []).join(', ') || 'General'}</strong>
            <span>Detailed event categories</span>
          </div>
        </section>
      </div>

      {mapFrameUrl && (
        <section className="map-card card soft-glow">
          <div className="section-header">
            <div>
              <p className="section-label">Location map</p>
              <h3>Geospatial visualization</h3>
            </div>
          </div>
          <iframe
            className="map-frame"
            title={`Map of ${report.location}`}
            src={mapFrameUrl}
            loading="lazy"
            sandbox="allow-same-origin allow-scripts allow-popups"
          />
          <div className="map-caption">Map coordinates: {report.coordinates.latitude}, {report.coordinates.longitude}</div>
          <a
            className="map-link"
            href={`https://www.openstreetmap.org/?mlat=${report.coordinates.latitude}&mlon=${report.coordinates.longitude}#map=10/${report.coordinates.latitude}/${report.coordinates.longitude}`}
            target="_blank"
            rel="noreferrer"
          >
            Open location in OpenStreetMap
          </a>
        </section>
      )}

      <section className="compare-card card soft-glow">
        <div className="section-header">
          <div>
            <p className="section-label">Compare cities</p>
            <h3>Multi-city risk comparison</h3>
          </div>
        </div>
        <div className="compare-row">
          <input
            value={compareInput}
            onChange={(event) => setCompareInput(event.target.value)}
            placeholder="Enter cities separated by commas"
            aria-label="City comparison input"
          />
          <button className="secondary-btn" onClick={compareRisk} disabled={compareLoading}>
            {compareLoading ? 'Comparing…' : 'Compare'}
          </button>
          <button className="ghost-btn" onClick={compareFavorites}>
            Compare favorites
          </button>
        </div>
        {compareResults.length > 0 && (
          <div className="compare-grid">
            {compareResults.map((item) => (
              <div key={item.location} className="compare-card-item">
                <h4>{item.location}</h4>
                <span className={`badge risk-${item.risk_level}`}>{item.risk_level}</span>
                <p>{item.risk_score}/100</p>
                <div className="compare-summary">
                  <span>{item.weather.condition}</span>
                  <span>{formatNumber(item.weather.temperature_c)}°C</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid-layout">
        <section className="report-card card soft-glow">
          <div className="section-header">
            <div>
              <p className="section-label">Snapshot</p>
              <h3>{report ? `Live report for ${report.location}` : 'No report yet'}</h3>
            </div>
            {report && (
              <button className="secondary-btn" onClick={handleCopy}>
                Copy report
              </button>
            )}
          </div>

          {error && <div className="alert-inline">{error}</div>}
          {statusMessage && <div className="status-note">{statusMessage}</div>}

          {report ? (
            <>
              <div className="report-grid">
                <div className="detail-box">
                  <p className="detail-label">Temperature</p>
                  <strong>{formatNumber(report.weather.temperature_c)}°C</strong>
                </div>
                <div className="detail-box">
                  <p className="detail-label">Humidity</p>
                  <strong>{formatNumber(report.weather.humidity_percent)}%</strong>
                </div>
                <div className="detail-box">
                  <p className="detail-label">Wind</p>
                  <strong>{formatNumber(report.weather.wind_speed_ms)} m/s</strong>
                </div>
                <div className="detail-box">
                  <p className="detail-label">Condition</p>
                  <strong>{report.weather.condition}</strong>
                </div>
              </div>

              <div className="detail-row">
                <div>
                  <p className="section-label">Event categories</p>
                  <div className="badge-row">
                    {(report.event_categories || []).map((category) => (
                      <span key={category} className="badge-category">{category}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="section-label">Details</p>
                  <div className="detail-list">
                    <span>Pressure: {formatNumber(report.weather.pressure_hpa)} hPa</span>
                    <span>Visibility: {formatNumber(report.weather.visibility_m)} m</span>
                    <span>Cloudiness: {formatNumber(report.weather.cloudiness_percent)}%</span>
                  </div>
                </div>
              </div>

              <div className="section">
                <p className="section-label">News alerts</p>
                {(report.news_alerts || []).length > 0 ? (
                  (report.news_alerts || []).map((alert, index) => (
                    <div key={index} className="alert-item">
                      {alert}
                    </div>
                  ))
                ) : (
                  <div className="alert-item empty">No recent disaster news found.</div>
                )}
              </div>

              <div className="section">
                <p className="section-label">Advice</p>
                {(report.advice || []).map((tip, index) => (
                  <div key={index} className="advice-item">
                    {tip}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="empty-state">Start with a question to see a glowing disaster report.</p>
          )}
        </section>

        <section className="history-card card soft-glow">
          <div className="section-header">
            <div>
              <p className="section-label">History</p>
              <h3>Risk trend</h3>
            </div>
          </div>

          {trendItems.length ? (
            <div className="trend-graph">
              {trendItems.map((item) => (
                <div key={item.timestamp} className="trend-bar-item">
                  <span>{item.location}</span>
                  <div className="trend-bar-wrapper">
                    <div className="trend-bar" style={{ width: `${item.risk_score}%` }} />
                  </div>
                  <strong>{item.risk_score}/100</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-state">Your recent risk trend will appear here.</p>
          )}
        </section>
      </div>
    </div>
  );
}
