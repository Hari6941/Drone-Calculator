import React from 'react';

export default function ViolationsList({ violations }) {
  if (!violations || violations.length === 0) return null;

  return (
    <div className="violations-panel">
      <div className="violations-title">
        <svg style={{ width: '18px', height: '18px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>Design Violations Detected ({violations.length})</span>
      </div>
      
      {violations.map((violation, index) => (
        <div key={index} className={`violation-card severity-${violation.severity}`}>
          <div className="violation-meta">
            <span className="violation-param">{violation.parameter}</span>
            <span className={`violation-severity ${violation.severity}`}>
              {violation.severity} Limit
            </span>
          </div>
          <div className="violation-message">
            The constraint for <strong>{violation.parameter}</strong> was violated. 
            Limit: {violation.limit} // Actual: {violation.actual}
          </div>
          {violation.suggestion && (
            <div className="violation-suggestion">
              💡 {violation.suggestion}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
