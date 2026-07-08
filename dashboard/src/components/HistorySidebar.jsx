import React from 'react';

export default function HistorySidebar({ historyList, activeDesignId, onSelectDesign, onNewDesign, historyLoading }) {
  const formatDate = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>
          <svg style={{ width: '16px', height: '16px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          History
        </h2>
        <button 
          onClick={onNewDesign}
          className="toggle-btn"
          style={{ padding: '0.35rem 0.65rem', border: '1px solid var(--border-color)', fontSize: '0.7rem' }}
        >
          + NEW RUN
        </button>
      </div>

      <div className="history-list">
        {historyLoading ? (
          <>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-item">
                <div className="skeleton-header">
                  <div className="skeleton-line id-skeleton"></div>
                  <div className="skeleton-line date-skeleton"></div>
                </div>
                <div className="skeleton-details">
                  <div className="skeleton-line detail-skeleton"></div>
                  <div className="skeleton-line detail-skeleton"></div>
                </div>
                <div className="skeleton-footer">
                  <div className="skeleton-badge"></div>
                  <div className="skeleton-airfoil"></div>
                </div>
              </div>
            ))}
          </>
        ) : historyList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            No recent design runs found.
          </div>
        ) : (
          historyList.map((run) => (
            <button
              key={run.id}
              className={`history-item ${activeDesignId === run.id ? 'active' : ''}`}
              onClick={() => onSelectDesign(run.id)}
            >
              <div className="history-item-header">
                <span className="history-id">{run.id}</span>
                <span className="history-date">{formatDate(run.created_at)}</span>
              </div>
              <div className="history-details" style={{ marginBottom: '0.4rem' }}>
                 <div>MTOW: {run.design ? `${run.design.MTOW_kg}kg` : '—'}</div>
                 <div>Span: {run.design ? `${run.design.span_m}m` : '—'}</div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className={`history-status-badge status-${run.status}`}>
                  {run.status.replace('_', ' ')}
                </span>
                {run.design && (
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {run.design.airfoil_id}
                  </span>
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
