import React, { useState } from 'react';

export default function DesignForm({ onSubmit, loading }) {
  const [rules, setRules] = useState({
    MTOW_kg: '5.0',
    payload_kg: '1.5',
    max_wingspan_m: '2.0',
    KV_rating: '1000',
    max_power_W: '500',
    min_stall_speed_ms: '',
    target_cruise_speed_ms: '15.0',
  });
  
  const [customAirfoilPaths, setCustomAirfoilPaths] = useState([]);
  const [useLlm, setUseLlm] = useState(true);
  const [maxIterations, setMaxIterations] = useState(10);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setRules((prev) => ({ ...prev, [name]: value }));
  };

  const handleAddAirfoilPath = () => {
    setCustomAirfoilPaths((prev) => [...prev, '']);
  };

  const handleAirfoilPathChange = (index, value) => {
    setCustomAirfoilPaths((prev) => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  };

  const handleRemoveAirfoilPath = (index) => {
    setCustomAirfoilPaths((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Construct payload strictly matching CompetitionRules schema
    const payloadRules = {
      MTOW_kg: rules.MTOW_kg ? parseFloat(rules.MTOW_kg) : null,
      payload_kg: rules.payload_kg ? parseFloat(rules.payload_kg) : null,
      max_wingspan_m: rules.max_wingspan_m ? parseFloat(rules.max_wingspan_m) : null,
      KV_rating: rules.KV_rating ? parseInt(rules.KV_rating, 10) : null,
      max_power_W: rules.max_power_W ? parseInt(rules.max_power_W, 10) : null,
      min_stall_speed_ms: rules.min_stall_speed_ms ? parseFloat(rules.min_stall_speed_ms) : null,
      target_cruise_speed_ms: rules.target_cruise_speed_ms ? parseFloat(rules.target_cruise_speed_ms) : 15.0,
      custom_airfoil_paths: customAirfoilPaths.filter(path => path.trim() !== '')
    };

    onSubmit(payloadRules, useLlm, maxIterations);
  };

  return (
    <div className="glass-card" style={{ height: '100%' }}>
      <div className="glass-card-title">
        <span>Design Parameters</span>
        <svg style={{ width: '20px', height: '20px', color: 'var(--accent-blue)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="MTOW_kg">
            Max Takeoff Weight (MTOW)
            <span>Required // kg</span>
          </label>
          <input
            id="MTOW_kg"
            name="MTOW_kg"
            type="number"
            step="0.1"
            min="0.1"
            required
            className="input-control"
            value={rules.MTOW_kg}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="payload_kg">
            Payload Weight
            <span>Required // kg</span>
          </label>
          <input
            id="payload_kg"
            name="payload_kg"
            type="number"
            step="0.1"
            min="0"
            required
            className="input-control"
            value={rules.payload_kg}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="max_wingspan_m">
            Max Wingspan Limit
            <span>Required // m</span>
          </label>
          <input
            id="max_wingspan_m"
            name="max_wingspan_m"
            type="number"
            step="0.05"
            min="0.2"
            required
            className="input-control"
            value={rules.max_wingspan_m}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="target_cruise_speed_ms">
            Target Cruise Speed
            <span>Optional // m/s (default 15.0)</span>
          </label>
          <input
            id="target_cruise_speed_ms"
            name="target_cruise_speed_ms"
            type="number"
            step="0.1"
            min="1"
            className="input-control"
            placeholder="15.0"
            value={rules.target_cruise_speed_ms}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="KV_rating">
            Motor KV Rating
            <span>Required // RPM/V</span>
          </label>
          <input
            id="KV_rating"
            name="KV_rating"
            type="number"
            min="50"
            step="10"
            required
            className="input-control"
            value={rules.KV_rating}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="max_power_W">
            Max Power Limit
            <span>Required // W</span>
          </label>
          <input
            id="max_power_W"
            name="max_power_W"
            type="number"
            min="10"
            step="5"
            required
            className="input-control"
            value={rules.max_power_W}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="min_stall_speed_ms">
            Stall Speed Limit
            <span>Optional // m/s</span>
          </label>
          <input
            id="min_stall_speed_ms"
            name="min_stall_speed_ms"
            type="number"
            step="0.1"
            min="1"
            className="input-control"
            placeholder="None"
            value={rules.min_stall_speed_ms}
            onChange={handleInputChange}
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label>
            Custom Airfoil Path(s)
            <span>Host Absolute Paths</span>
          </label>
          <div className="airfoil-paths-list">
            {customAirfoilPaths.map((path, idx) => (
              <div key={idx} className="airfoil-path-row">
                <input
                  type="text"
                  placeholder="e.g. C:/airfoils/custom.dat"
                  className="input-control"
                  value={path}
                  onChange={(e) => handleAirfoilPathChange(idx, e.target.value)}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => handleRemoveAirfoilPath(idx)}
                  className="btn-remove"
                  title="Remove path"
                  disabled={loading}
                  aria-label={`Remove airfoil path ${idx + 1}`}
                >
                  <svg style={{ width: '16px', height: '16px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={handleAddAirfoilPath}
            className="btn-add"
            disabled={loading}
          >
            + Add Custom Airfoil Path
          </button>
        </div>

        <div className="form-group" style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                disabled={loading}
              />
              Enable AI Orchestration
            </label>
          </div>
          
          <div>
            <label htmlFor="max_iterations" style={{ marginBottom: '0.25rem' }}>
              Max Iterations
              <span>{maxIterations}</span>
            </label>
            <input
              id="max_iterations"
              type="range"
              min="1"
              max="20"
              style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
              value={maxIterations}
              onChange={(e) => setMaxIterations(parseInt(e.target.value, 10))}
              disabled={loading}
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={loading}
          style={{ marginTop: '1rem' }}
        >
          {loading ? (
            <>
              <svg className="spinner" viewBox="0 0 50 50">
                <circle className="path" cx="25" cy="25" r="20" fill="none" strokeWidth="5"></circle>
              </svg>
              Optimizing Design...
            </>
          ) : (
            <>
              <svg style={{ width: '18px', height: '18px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Run Optimization
            </>
          )}
        </button>
      </form>
    </div>
  );
}
