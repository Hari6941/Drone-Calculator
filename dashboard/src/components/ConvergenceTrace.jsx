import React, { useState } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  ReferenceLine 
} from 'recharts';

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={{
        background: '#0A0A0A',
        border: '1px dashed rgba(255, 255, 255, 0.25)',
        padding: '0.6rem 0.8rem',
        fontSize: '0.8rem',
        fontFamily: 'var(--font-sans)',
        color: '#ffffff'
      }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, marginBottom: '0.3rem', textTransform: 'uppercase', color: 'var(--accent-cyan)' }}>
          Step {data.iteration}
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginBottom: '0.15rem' }}>
          L/D Ratio: <span style={{ color: '#fff', fontWeight: 600 }}>{data.L_D_ratio.toFixed(2)}</span>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginBottom: '0.15rem' }}>
          Wingspan: <span style={{ color: '#fff', fontWeight: 600 }}>{data.span_m.toFixed(2)}m</span>
        </div>
        {data.violations && data.violations.length > 0 && (
          <div style={{ color: 'var(--status-danger)', fontSize: '0.7rem', marginTop: '0.3rem', fontWeight: 600 }}>
            ⚠️ {data.violations.length} VIOLATION(S)
          </div>
        )}
      </div>
    );
  }
  return null;
};

export default function ConvergenceTrace({ history, rules }) {
  const [hoveredStep, setHoveredStep] = useState(null);

  if (!history || history.length === 0) {
    return (
      <div className="empty-state">
        <h3>No History Available</h3>
        <p>Run an optimization to view the convergence trace.</p>
      </div>
    );
  }

  const MTOW = rules ? parseFloat(rules.MTOW_kg) || 5.0 : 5.0;
  const wingspanLimit = rules ? parseFloat(rules.max_wingspan_m) || 2.0 : 2.0;

  // Helper to extract or calculate L_D_ratio and span_m for each step
  const plotData = history.map((step) => {
    const vars = step.design_variables || {};
    
    // Calculate span_m if not present: span_m = sqrt(AR * S_m2)
    const AR = parseFloat(vars.AR || vars.aspect_ratio || 5.0);
    const S = parseFloat(vars.S_m2 || vars.wing_area_m2 || 0.5);
    const calculatedSpan = Math.sqrt(AR * S);
    const span_m = parseFloat(vars.span_m !== undefined ? vars.span_m : calculatedSpan);

    // Calculate L_D_ratio if not present
    let L_D_ratio = parseFloat(vars.L_D_ratio);
    if (isNaN(L_D_ratio)) {
      const V = parseFloat(vars.V_cruise_ms || 15.0);
      const e = parseFloat(vars.e || 0.8);
      const CD0 = parseFloat(vars.CD0 || 0.02);
      const W = MTOW * 9.80665;
      const CL = (2 * W) / (1.225 * V * V * S);
      const CD = CD0 + (CL * CL) / (Math.PI * AR * e);
      L_D_ratio = CL / CD;
    }

    return {
      iteration: step.iteration,
      span_m: isNaN(span_m) ? 1.5 : span_m,
      L_D_ratio: isNaN(L_D_ratio) ? 12.0 : L_D_ratio,
      reasoning: step.reasoning,
      violations: step.violations || [],
      variables: vars
    };
  });

  const ldValues = plotData.map(d => d.L_D_ratio);
  const minLd = Math.max(0, Math.min(...ldValues) - 2);
  const maxLd = Math.max(...ldValues) + 2;

  const spanValues = plotData.map(d => d.span_m);
  const minSpan = Math.max(0, Math.min(...spanValues) - 0.5);
  const maxSpan = Math.max(...spanValues, wingspanLimit) + 0.5;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Recharts Convergence Chart */}
      <div className="chart-container">
        <div className="chart-title">
          <span>Aerodynamic Efficiency vs. Wingspan Convergence</span>
          <div className="chart-legend">
            <div className="legend-item">
              <span className="legend-color" style={{ background: '#ffffff' }}></span>
              <span style={{ color: '#ffffff' }}>L/D Ratio</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: 'var(--text-secondary)', borderBottom: '1px dashed var(--text-secondary)' }}></span>
              <span style={{ color: 'var(--text-secondary)' }}>Wingspan (m)</span>
            </div>
          </div>
        </div>

        <div style={{ width: '100%', height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={plotData}
              margin={{ top: 20, right: 10, left: 0, bottom: 5 }}
              onMouseMove={(state) => {
                if (state && state.activeTooltipIndex !== undefined) {
                  setHoveredStep(plotData[state.activeTooltipIndex].iteration);
                }
              }}
              onMouseLeave={() => {
                setHoveredStep(null);
              }}
            >
              <CartesianGrid stroke="rgba(255, 255, 255, 0.05)" strokeDasharray="2 2" />
              <XAxis 
                dataKey="iteration" 
                stroke="var(--text-muted)" 
                tick={{ fill: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 'bold' }}
                tickFormatter={(v) => `Step ${v}`}
              />
              <YAxis 
                yAxisId="left"
                domain={[minLd, maxLd]}
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-primary)', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                label={{ value: 'L/D Ratio', angle: -90, position: 'insideLeft', offset: 12, fill: '#ffffff', fontSize: 10, fontFamily: 'var(--font-display)', fontWeight: 600 }}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                domain={[minSpan, maxSpan]}
                stroke="var(--text-muted)"
                tick={{ fill: 'var(--text-secondary)', fontSize: 9, fontFamily: 'var(--font-mono)' }}
                label={{ value: 'Wingspan (m)', angle: 90, position: 'insideRight', offset: 5, fill: 'var(--text-secondary)', fontSize: 10, fontFamily: 'var(--font-display)', fontWeight: 600 }}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255, 255, 255, 0.05)', strokeWidth: 1 }} />
              <ReferenceLine 
                y={wingspanLimit} 
                yAxisId="right" 
                stroke="var(--accent-red)" 
                strokeDasharray="3 3"
                label={{ value: `Limit: ${wingspanLimit.toFixed(2)}m`, fill: 'var(--accent-red)', position: 'top', fontSize: 9, fontFamily: 'var(--font-mono)', offset: 5 }}
              />
              <Line 
                yAxisId="left"
                type="monotone" 
                dataKey="L_D_ratio" 
                stroke="#ffffff" 
                strokeWidth={2}
                activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 1 }}
                dot={{ r: 4, stroke: '#ffffff', strokeWidth: 1, fill: '#000000' }}
                animationDuration={300}
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="span_m" 
                stroke="var(--text-secondary)" 
                strokeDasharray="3 3"
                strokeWidth={2}
                activeDot={{ r: 6, stroke: 'var(--text-secondary)', strokeWidth: 1 }}
                dot={{ r: 4, stroke: 'var(--text-secondary)', strokeWidth: 1, fill: '#000000' }}
                animationDuration={300}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Vertical Stepper timeline */}
      <div>
        <h3 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
          Iteration-by-Iteration Convergence Log
        </h3>
        <div className="trace-timeline">
          {plotData.map((step, idx) => {
            const hasViolations = step.violations.length > 0;
            
            return (
              <div 
                key={idx} 
                className={`trace-step ${hasViolations ? 'has-violations' : ''} ${hoveredStep === step.iteration ? 'active-highlight' : ''}`}
              >
                <div className="trace-node"></div>
                <div className="trace-card">
                  <div className="trace-step-header">
                    <span className="trace-step-num">Step {step.iteration}</span>
                    {hasViolations ? (
                      <span className="history-status-badge status-best_effort" style={{ fontSize: '0.6rem' }}>
                        Violations ({step.violations.length})
                      </span>
                    ) : (
                      <span className="history-status-badge status-converged" style={{ fontSize: '0.6rem' }}>
                        Satisfied
                      </span>
                    )}
                  </div>
                  
                  {step.reasoning && (
                    <div className="trace-reasoning">
                      {step.reasoning}
                    </div>
                  )}

                  {/* Show Violations directly in this step if they occurred */}
                  {hasViolations && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', margin: '0.6rem 0' }}>
                      {step.violations.map((violation, vIdx) => (
                        <div 
                          key={vIdx} 
                          style={{ 
                            fontSize: '0.75rem', 
                            padding: '0.4rem 0.6rem', 
                            background: 'transparent',
                            border: `1px dashed ${violation.severity === 'hard' ? 'var(--accent-red)' : 'rgba(255, 255, 255, 0.15)'}`,
                            color: violation.severity === 'hard' ? 'var(--accent-red)' : 'var(--text-secondary)',
                            borderRadius: '0px',
                            marginBottom: '0.25rem'
                          }}
                        >
                          <strong style={{ textTransform: 'uppercase' }}>
                            {violation.severity} violation:
                          </strong>{' '}
                          {violation.parameter} limit is {violation.limit}, actual was {violation.actual}.
                          <span style={{ display: 'block', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                            💡 {violation.suggestion}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="trace-step-variables">
                    {Object.entries(step.variables).map(([k, v]) => {
                      if (typeof v !== 'number') return null;
                      return (
                        <span key={k}>
                          <strong>{k}:</strong> {k === 'Re' ? v.toLocaleString() : v.toFixed(3)}
                        </span>
                      );
                    })}
                    <span>
                      <strong>span_m:</strong> {step.span_m.toFixed(2)}m
                    </span>
                    <span>
                      <strong>L/D:</strong> {step.L_D_ratio.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
