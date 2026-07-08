import React from 'react';

export default function DesignResults({ data }) {
  if (!data) return null;

  const { status, iterations_used, design, design_variables } = data;

  const getStatusLabel = (status) => {
    switch (status) {
      case 'converged': return 'Converged';
      case 'best_effort': return 'Best Effort';
      case 'no_viable_airfoil': return 'Optimization Failed';
      default: return status;
    }
  };

  const keysLabels = {
    wing_area_m2: { label: 'Wing Area', unit: 'm²' },
    aspect_ratio: { label: 'Aspect Ratio', unit: 'dim' },
    airfoil_id: { label: 'Selected Airfoil', unit: 'id' },
    CL_cruise: { label: 'CL Cruise', unit: 'dim' },
    CD_total: { label: 'CD Total', unit: 'dim' },
    MTOW_kg: { label: 'Takeoff Weight', unit: 'kg' },
    stall_speed_ms: { label: 'Stall Speed', unit: 'm/s' },
    L_D_ratio: { label: 'L/D Ratio', unit: 'dim' },
    span_m: { label: 'Wingspan', unit: 'm' },
    power_required_W: { label: 'Required Power', unit: 'W' }
  };

  const varLabels = {
    V_cruise_ms: { label: 'Cruise Velocity (V_cruise)', unit: 'm/s' },
    S_m2: { label: 'Reference Area (S)', unit: 'm²' },
    AR: { label: 'Aspect Ratio (AR)', unit: 'dim' },
    e: { label: 'Oswald Efficiency (e)', unit: 'dim' },
    CD0: { label: 'Parasite Drag (CD0)', unit: 'dim' },
    CL_max: { label: 'Max Lift Coefficient (CL_max)', unit: 'dim' },
    Re: { label: 'Reynolds Number (Re)', unit: 'dim' }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <h2 style={{ fontSize: '1.2rem', fontWeight: '700' }}>Active Optimization Output</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            ITERATIONS: {iterations_used}
          </span>
          <span className={`history-status-badge status-${status}`}>
            {getStatusLabel(status)}
          </span>
        </div>
      </div>

      {design ? (
        <>
          <div className="results-grid">
            {Object.entries(keysLabels).map(([key, meta]) => {
              const val = design[key];
              const displayVal = typeof val === 'number' ? val.toFixed(key === 'Re' ? 0 : 3) : val;

              return (
                <div key={key} className="metric-card">
                  <span className="metric-label">{meta.label}</span>
                  <span className="metric-value">{displayVal}</span>
                  <span className="metric-unit">{meta.unit === 'dim' ? 'dimensionless' : meta.unit}</span>
                </div>
              );
            })}
          </div>

          {design_variables && (
            <div className="variables-section">
              <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Optimization Design Variables
              </h3>
              <table className="variables-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>Value</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(varLabels).map(([key, meta]) => {
                    const val = design_variables[key];
                    const displayVal = typeof val === 'number' ? (key === 'Re' ? val.toLocaleString() : val.toFixed(4)) : val;

                    return (
                      <tr key={key}>
                        <td className="name">{meta.label}</td>
                        <td>{displayVal}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{meta.unit}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state" style={{ background: 'rgba(239, 68, 68, 0.02)', border: '1px dashed rgba(239, 68, 68, 0.2)', borderRadius: '12px' }}>
          <div className="empty-state-icon" style={{ color: 'var(--danger)' }}>
            <svg style={{ width: '48px', height: '48px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3>Optimization Failed</h3>
          <p>
            No aerodynamic solution could be found matching the requested constraints. 
            Check the <strong>Convergence Trace</strong> tab to analyze how the parameters drifted.
          </p>
        </div>
      )}
    </div>
  );
}
