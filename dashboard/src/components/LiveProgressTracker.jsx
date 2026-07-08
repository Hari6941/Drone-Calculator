import React, { useEffect, useRef } from 'react';

const NODE_DISPLAY_NAMES = {
  ingest_rules: 'Ingest Rules',
  seed_design: 'Seed Design',
  evaluate_aero: 'Evaluate Aero',
  select_airfoil: 'Select Airfoil',
  check_constraints: 'Check Constraints',
  adjust_design: 'Adjust Design',
  finalize_design: 'Finalize Design'
};

const ALL_NODES = [
  'ingest_rules',
  'seed_design',
  'evaluate_aero',
  'select_airfoil',
  'check_constraints',
  'adjust_design',
  'finalize_design'
];

export default function LiveProgressTracker({ progress }) {
  const consoleEndRef = useRef(null);

  // Auto-scroll the logs terminal to the bottom when new logs arrive
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [progress.logs]);

  const { currentNode, completedNodes, logs, airfoilEvaluations, currentVariables } = progress;

  return (
    <div className="live-tracker-panel">
      {/* Header with status */}
      <div className="tracker-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div className="pulse-indicator"></div>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>
              Live Optimization Active
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Agentic design loop executing...
            </span>
          </div>
        </div>
        {currentNode && (
          <span className="current-node-badge">
            RUNNING: {NODE_DISPLAY_NAMES[currentNode] || currentNode}
          </span>
        )}
      </div>

      {/* Visual Workflow Flow Map */}
      <div className="workflow-flow-map">
        {ALL_NODES.map((node, idx) => {
          const isCompleted = completedNodes.includes(node);
          const isActive = currentNode === node;
          let nodeClass = 'flow-node-pending';
          if (isCompleted) nodeClass = 'flow-node-completed';
          if (isActive) nodeClass = 'flow-node-active';

          return (
            <React.Fragment key={node}>
              <div className={`flow-node ${nodeClass}`}>
                <div className="node-marker">
                  {isCompleted ? '✓' : idx + 1}
                </div>
                <span className="node-label">{NODE_DISPLAY_NAMES[node]}</span>
              </div>
              {idx < ALL_NODES.length - 1 && (
                <div className={`flow-connector ${isCompleted ? 'connector-completed' : ''} ${isActive ? 'connector-active' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Grid containing Airfoil evaluations and Current variables */}
      <div className="tracker-grid">
        {/* Left Side: Airfoil Candidate Status Radar */}
        <div className="tracker-card">
          <h4 className="tracker-card-title">Airfoil Candidate Evaluations</h4>
          {Object.keys(airfoilEvaluations).length === 0 ? (
            <div className="empty-radar">
              Waiting for select_airfoil node...
            </div>
          ) : (
            <div className="airfoil-radar-list">
              {Object.entries(airfoilEvaluations).map(([id, item]) => {
                let badgeClass = 'status-pending';
                let label = 'Evaluating...';
                if (item.status === 'passed') {
                  badgeClass = 'status-passed';
                  label = `PASS (Score: ${item.details?.score?.toFixed(1)})`;
                } else if (item.status === 'skipped_thickness') {
                  badgeClass = 'status-skipped';
                  label = `SKIP (t/c ${item.details?.thickness?.toFixed(3)} > ${item.details?.max_thickness?.toFixed(2)})`;
                } else if (item.status === 'skipped_margin') {
                  badgeClass = 'status-skipped';
                  label = `SKIP (Margin ${item.details?.cl_margin?.toFixed(2)} < ${item.details?.min_margin?.toFixed(2)})`;
                } else if (item.status === 'skipped_interpolate') {
                  badgeClass = 'status-skipped';
                  label = 'SKIP (XFOIL Convergence Fail)';
                } else if (item.status === 'error') {
                  badgeClass = 'status-error';
                  label = `ERROR: ${item.details?.error}`;
                }

                return (
                  <div key={id} className="airfoil-radar-row">
                    <span className="airfoil-name">{id}</span>
                    <span className={`airfoil-badge ${badgeClass}`}>{label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Side: Current Design Variables */}
        <div className="tracker-card">
          <h4 className="tracker-card-title">Live Design Attributes</h4>
          <div className="metrics-tracker-grid">
            <div className="metric-tracker-box">
              <span className="metric-box-label">MTOW</span>
              <span className="metric-box-value">
                {currentVariables.MTOW_kg ? `${currentVariables.MTOW_kg.toFixed(2)} kg` : '—'}
              </span>
            </div>
            <div className="metric-tracker-box">
              <span className="metric-box-label">Wing Area</span>
              <span className="metric-box-value">
                {currentVariables.wing_area_m2 ? `${currentVariables.wing_area_m2.toFixed(3)} m²` : '—'}
              </span>
            </div>
            <div className="metric-tracker-box">
              <span className="metric-box-label">Wingspan</span>
              <span className="metric-box-value">
                {currentVariables.span_m ? `${currentVariables.span_m.toFixed(2)} m` : '—'}
              </span>
            </div>
            <div className="metric-tracker-box">
              <span className="metric-box-label">Cruise Speed</span>
              <span className="metric-box-value">
                {currentVariables.V_cruise_ms ? `${currentVariables.V_cruise_ms.toFixed(1)} m/s` : '—'}
              </span>
            </div>
            <div className="metric-tracker-box">
              <span className="metric-box-label">Stall Speed</span>
              <span className="metric-box-value">
                {currentVariables.stall_speed_ms ? `${currentVariables.stall_speed_ms.toFixed(1)} m/s` : '—'}
              </span>
            </div>
            <div className="metric-tracker-box">
              <span className="metric-box-label">Power Required</span>
              <span className="metric-box-value">
                {currentVariables.power_required_W ? `${currentVariables.power_required_W.toFixed(1)} W` : '—'}
              </span>
            </div>
          </div>
          <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <strong>Selected Airfoil:</strong> {currentVariables.airfoil_id || 'None'}
            {currentVariables.converged && (
              <span className="history-status-badge status-converged" style={{ marginLeft: '0.5rem', fontSize: '0.65rem' }}>
                CONVERGED
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Monospace terminal console for logs */}
      <div className="logs-console">
        <div className="console-header">
          <span>Optimization Console Logs</span>
          <span className="console-dot-blink"></span>
        </div>
        <div className="console-body">
          {logs.map((log, idx) => (
            <div key={idx} className={`console-line line-${log.type}`}>
              <span className="console-timestamp">[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
              <span className="console-text">{log.text}</span>
            </div>
          ))}
          <div ref={consoleEndRef} />
        </div>
      </div>
    </div>
  );
}
