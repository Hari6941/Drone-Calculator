import React from 'react';

export default function Header({ mockMode, setMockMode, mockScenario, setMockScenario }) {
  return (
    <header className="dashboard-header">
      <div className="header-title-section">
        <h1>UAV DESIGN INTELLIGENCE SYSTEM</h1>
        <div className="header-subtitle">Phase 5 // Design Optimizer & Analytics Dashboard</div>
      </div>
      
      <div className="header-controls">
        {mockMode && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>SCENARIO:</span>
            <select 
              value={mockScenario} 
              onChange={(e) => setMockScenario(e.target.value)}
              className="input-control"
              style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', width: 'auto', background: 'rgba(6, 182, 212, 0.1)', borderColor: 'rgba(6, 182, 212, 0.3)' }}
            >
              <option value="converged">Converged (Success)</option>
              <option value="best_effort">Best Effort (Max Iterations)</option>
              <option value="no_viable_airfoil">No Viable Airfoil (Failure)</option>
              <option value="validation_422">422 Custom Airfoil Reject</option>
              <option value="bad_request_400">400 Bad Request</option>
              <option value="server_error_500">500 Server Error</option>
            </select>
          </div>
        )}

        <div className="toggle-container">
          <button 
            className={`toggle-btn ${mockMode ? 'active mock-active' : ''}`}
            onClick={() => setMockMode(true)}
            title="Use simulated backend payloads for offline development"
          >
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor', marginRight: '4px' }}></span>
            MOCK MODE
          </button>
          <button 
            className={`toggle-btn ${!mockMode ? 'active' : ''}`}
            onClick={() => setMockMode(false)}
            title="Connect directly to the FastAPI server at /api/v1"
          >
            LIVE API
          </button>
        </div>
      </div>
    </header>
  );
}
