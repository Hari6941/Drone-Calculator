import React, { useState } from 'react';

export default function ConvergenceTrace({ history, rules }) {
  const [hoveredDot, setHoveredDot] = useState(null); // { type, index }

  if (!history || history.length === 0) {
    return (
      <div className="empty-state">
        <h3>No History Available</h3>
        <p>Run an optimization to view the convergence trace.</p>
      </div>
    );
  }

  const MTOW = rules ? parseFloat(rules.MTOW_kg) || 5.0 : 5.0;

  // Helper to extract or calculate L_D_ratio and span_m for each step
  const plotData = history.map((step) => {
    const vars = step.design_variables || {};
    
    // Calculate span_m if not present: span_m = sqrt(AR * S_m2)
    const AR = parseFloat(vars.AR || vars.aspect_ratio || 5.0);
    const S = parseFloat(vars.S_m2 || vars.wing_area_m2 || 0.5);
    const calculatedSpan = Math.sqrt(AR * S);
    const span_m = parseFloat(vars.span_m !== undefined ? vars.span_m : calculatedSpan);

    // Calculate L_D_ratio if not present:
    // CL = 2*W / (rho * V^2 * S)
    // CD = CD0 + CL^2 / (pi * AR * e)
    // LD = CL / CD
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

  // SVG Chart Calculations
  const chartWidth = 600;
  const chartHeight = 220;
  const paddingLeft = 50;
  const paddingRight = 50;
  const paddingTop = 20;
  const paddingBottom = 30;

  const innerWidth = chartWidth - paddingLeft - paddingRight;
  const innerHeight = chartHeight - paddingTop - paddingBottom;

  const iterations = plotData.map(d => d.iteration);
  const minIter = iterations[0] || 1;
  const maxIter = iterations[iterations.length - 1] || 1;
  
  // Scales
  const getX = (iter) => {
    if (maxIter === minIter) return paddingLeft + innerWidth / 2;
    return paddingLeft + ((iter - minIter) / (maxIter - minIter)) * innerWidth;
  };

  // Left Y scale (L_D_ratio)
  const ldValues = plotData.map(d => d.L_D_ratio);
  const minLd = Math.max(0, Math.min(...ldValues) - 2);
  const maxLd = Math.max(...ldValues) + 2;
  const getYLd = (ld) => {
    if (maxLd === minLd) return paddingTop + innerHeight / 2;
    return paddingTop + innerHeight - ((ld - minLd) / (maxLd - minLd)) * innerHeight;
  };

  // Right Y scale (span_m)
  const spanValues = plotData.map(d => d.span_m);
  const minSpan = Math.max(0, Math.min(...spanValues) - 0.5);
  const maxSpan = Math.max(...spanValues) + 0.5;
  const getYSpan = (span) => {
    if (maxSpan === minSpan) return paddingTop + innerHeight / 2;
    return paddingTop + innerHeight - ((span - minSpan) / (maxSpan - minSpan)) * innerHeight;
  };

  // Draw lines
  let ldPath = '';
  let spanPath = '';

  plotData.forEach((d, i) => {
    const x = getX(d.iteration);
    const yLd = getYLd(d.L_D_ratio);
    const ySpan = getYSpan(d.span_m);

    if (i === 0) {
      ldPath = `M ${x} ${yLd}`;
      spanPath = `M ${x} ${ySpan}`;
    } else {
      ldPath += ` L ${x} ${yLd}`;
      spanPath += ` L ${x} ${ySpan}`;
    }
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* SVG Convergence Chart */}
      <div className="chart-container">
        <div className="chart-title">
          <span>Aerodynamic Efficiency vs. Wingspan Convergence</span>
          <div className="chart-legend">
            <div className="legend-item">
              <span className="legend-color" style={{ background: 'var(--accent-cyan)' }}></span>
              <span style={{ color: 'var(--accent-cyan)' }}>L/D Ratio</span>
            </div>
            <div className="legend-item">
              <span className="legend-color" style={{ background: 'var(--warning)', borderBottom: '1px dashed var(--warning)' }}></span>
              <span style={{ color: 'var(--warning)' }}>Wingspan (m)</span>
            </div>
          </div>
        </div>

        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="chart-svg">
          {/* Grid lines (X & Y) */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const y = paddingTop + ratio * innerHeight;
            return (
              <line 
                key={`grid-y-${idx}`}
                x1={paddingLeft} 
                y1={y} 
                x2={chartWidth - paddingRight} 
                y2={y} 
                className="chart-grid-line"
              />
            );
          })}

          {plotData.map((d, idx) => {
            const x = getX(d.iteration);
            return (
              <line
                key={`grid-x-${idx}`}
                x1={x}
                y1={paddingTop}
                x2={x}
                y2={paddingTop + innerHeight}
                className="chart-grid-line"
              />
            );
          })}

          {/* Left Y-axis ticks & labels (L/D) */}
          {[minLd, (minLd + maxLd) / 2, maxLd].map((val, idx) => {
            const y = getYLd(val);
            return (
              <text 
                key={`tick-ld-${idx}`} 
                x={paddingLeft - 10} 
                y={y + 4} 
                textAnchor="end" 
                className="chart-axis-label"
              >
                {val.toFixed(1)}
              </text>
            );
          })}

          {/* Right Y-axis ticks & labels (Span) */}
          {[minSpan, (minSpan + maxSpan) / 2, maxSpan].map((val, idx) => {
            const y = getYSpan(val);
            return (
              <text 
                key={`tick-span-${idx}`} 
                x={chartWidth - paddingRight + 10} 
                y={y + 4} 
                textAnchor="start" 
                className="chart-axis-label"
              >
                {val.toFixed(2)}m
              </text>
            );
          })}

          {/* X-axis labels (Iterations) */}
          {plotData.map((d, idx) => {
            const x = getX(d.iteration);
            return (
              <text
                key={`tick-x-${idx}`}
                x={x}
                y={chartHeight - 10}
                textAnchor="middle"
                className="chart-axis-label"
                style={{ fontWeight: 'bold' }}
              >
                Step {d.iteration}
              </text>
            );
          })}

          {/* Line paths */}
          {plotData.length > 1 && (
            <>
              <path d={ldPath} className="chart-line-ld" />
              <path d={spanPath} className="chart-line-span" />
            </>
          )}

          {/* Interactivity & Dots */}
          {plotData.map((d, idx) => {
            const x = getX(d.iteration);
            const yLd = getYLd(d.L_D_ratio);
            const ySpan = getYSpan(d.span_m);

            return (
              <g key={`dots-${idx}`}>
                {/* L/D Dot */}
                <circle
                  cx={x}
                  cy={yLd}
                  r={hoveredDot?.type === 'ld' && hoveredDot?.index === idx ? 6 : 4}
                  className="chart-dot-ld"
                  onMouseEnter={() => setHoveredDot({ type: 'ld', index: idx })}
                  onMouseLeave={() => setHoveredDot(null)}
                />
                
                {/* Span Dot */}
                <circle
                  cx={x}
                  cy={ySpan}
                  r={hoveredDot?.type === 'span' && hoveredDot?.index === idx ? 6 : 4}
                  className="chart-dot-span"
                  onMouseEnter={() => setHoveredDot({ type: 'span', index: idx })}
                  onMouseLeave={() => setHoveredDot(null)}
                />

                {/* Simple Tooltip on hovered point */}
                {hoveredDot?.index === idx && (
                  <g transform={`translate(${x > chartWidth - 120 ? x - 130 : x + 10}, ${yLd - 20})`} zIndex={100}>
                    <rect
                      width="120"
                      height="50"
                      rx="6"
                      fill="rgba(17, 24, 39, 0.95)"
                      stroke="var(--border-color)"
                      strokeWidth="1"
                    />
                    <text x="10" y="20" fill="var(--text-primary)" fontSize="10" fontFamily="var(--font-sans)" fontWeight="700">
                      Step {d.iteration} Data
                    </text>
                    <text x="10" y="32" fill="var(--accent-cyan)" fontSize="9" fontFamily="var(--font-mono)">
                      L/D: {d.L_D_ratio.toFixed(2)}
                    </text>
                    <text x="10" y="42" fill="var(--warning)" fontSize="9" fontFamily="var(--font-mono)">
                      Span: {d.span_m.toFixed(2)}m
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Vertical Stepper timeline */}
      <div>
        <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
          Iteration-by-Iteration Convergence Log
        </h3>
        <div className="trace-timeline">
          {plotData.map((step, idx) => {
            const hasViolations = step.violations.length > 0;
            
            return (
              <div 
                key={idx} 
                className={`trace-step ${hasViolations ? 'has-violations' : ''}`}
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
                            background: violation.severity === 'hard' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(249, 115, 22, 0.05)',
                            borderLeft: `2px solid ${violation.severity === 'hard' ? 'var(--danger)' : 'var(--warning)'}`,
                            borderRadius: '0 4px 4px 0'
                          }}
                        >
                          <strong style={{ color: violation.severity === 'hard' ? 'var(--danger)' : 'var(--warning)', textTransform: 'uppercase' }}>
                            {violation.severity} violation:
                          </strong>{' '}
                          {violation.parameter} limit is {violation.limit}, actual was {violation.actual}.
                          <span style={{ display: 'block', fontStyle: 'italic', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
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
