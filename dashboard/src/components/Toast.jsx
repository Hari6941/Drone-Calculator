import React from 'react';

export default function Toast({ error, success, onClose }) {
  if (!error && !success) return null;

  const isError = !!error;
  const title = isError ? 'Execution Error' : 'Success';
  
  // Format error messages nicely
  let message = '';
  let details = null;

  if (isError) {
    if (typeof error === 'string') {
      message = error;
    } else if (error.detail) {
      if (Array.isArray(error.detail)) {
        // FastAPI validation error (422)
        message = 'Input validation failed. Please check the parameters.';
        details = error.detail.map((err) => {
          const path = err.loc ? err.loc.join(' → ') : '';
          return `${path ? `[${path}]: ` : ''}${err.msg}`;
        }).join('\n');
      } else {
        // Generic detail error
        message = error.detail;
      }
    } else {
      message = 'An unexpected error occurred. Please try again.';
    }
  } else {
    message = success;
  }

  return (
    <div className="toast-container">
      <div className={`toast ${isError ? 'toast-error' : 'toast-success'}`}>
        <div className="toast-icon">
          {isError ? (
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          ) : (
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>
        <div className="toast-content">
          <div className="toast-title">{title}</div>
          <div className="toast-msg">{message}</div>
          {details && (
            <div className="toast-details">
              {details}
            </div>
          )}
        </div>
        <button className="toast-close" onClick={onClose} aria-label="Close message">
          <svg style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
