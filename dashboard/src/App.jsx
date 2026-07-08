import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import HistorySidebar from './components/HistorySidebar';
import DesignForm from './components/DesignForm';
import DesignResults from './components/DesignResults';
import ConvergenceTrace from './components/ConvergenceTrace';
import ViolationsList from './components/ViolationsList';
import Toast from './components/Toast';
import LiveProgressTracker from './components/LiveProgressTracker';
import { api } from './services/api';

export default function App() {
  const [mockMode, setMockMode] = useState(true);
  const [mockScenario, setMockScenario] = useState('converged');
  const [activeDesign, setActiveDesign] = useState(null);
  const [activeDesignId, setActiveDesignId] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [streamProgress, setStreamProgress] = useState(null);
  
  // Toast state: { error: data_object } or { success: message_string }
  const [toastMessage, setToastMessage] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  // Load history list on startup and when mockMode changes
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    const res = await api.getHistory(mockMode);
    setHistoryLoading(false);
    if (res.ok) {
      setHistoryList(res.data);
    } else {
      setToastMessage({ error: res.data });
    }
  }, [mockMode]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleRunDesign = async (rules, useLlm, maxIterations) => {
    if (loading) return;
    setLoading(true);
    setToastMessage(null);
    
    // If not in history mode, reset activeDesignId
    setActiveDesignId(null);

    // Initialize stream progress state
    setStreamProgress({
      currentNode: null,
      completedNodes: [],
      logs: [],
      airfoilEvaluations: {},
      currentVariables: {}
    });

    const onProgress = (event) => {
      setStreamProgress((prev) => {
        if (!prev) return prev;
        const updated = { ...prev };
        
        if (event.type === 'status') {
          updated.logs = [...updated.logs, { text: event.message, type: 'status' }];
        } else if (event.type === 'node_start') {
          updated.currentNode = event.node;
          updated.logs = [...updated.logs, { text: `Running node: ${event.node}...`, type: 'start' }];
        } else if (event.type === 'node_complete') {
          updated.completedNodes = [...updated.completedNodes, event.node];
          if (event.variables) {
            updated.currentVariables = { ...updated.currentVariables, ...event.variables };
          }
          updated.logs = [...updated.logs, { text: `Completed node: ${event.node}.`, type: 'complete' }];
        } else if (event.type === 'airfoil_progress') {
          updated.airfoilEvaluations = {
            ...updated.airfoilEvaluations,
            [event.airfoil_id]: { status: event.status, details: event.details }
          };
          
          let logMsg = `Evaluating candidate: ${event.airfoil_id}...`;
          if (event.status === 'passed') {
            logMsg = `Passed candidate: ${event.airfoil_id} (Score: ${event.details?.score?.toFixed(2)}, L/D: ${event.details?.L_D?.toFixed(1)})`;
          } else if (event.status === 'skipped_thickness') {
            logMsg = `Skipped candidate: ${event.airfoil_id} (thickness ratio ${event.details?.thickness?.toFixed(3)} exceeds max ${event.details?.max_thickness})`;
          } else if (event.status === 'skipped_margin') {
            logMsg = `Skipped candidate: ${event.airfoil_id} (lift margin ${event.details?.cl_margin?.toFixed(3)} is below required ${event.details?.min_margin})`;
          } else if (event.status === 'skipped_interpolate') {
            logMsg = `Skipped candidate: ${event.airfoil_id} (failed to interpolate CD at target cruise CL)`;
          } else if (event.status === 'error') {
            logMsg = `Error evaluating candidate: ${event.airfoil_id} - ${event.details?.error}`;
          }
          updated.logs = [...updated.logs, { text: logMsg, type: 'airfoil' }];
        }
        return updated;
      });
    };

    const res = await api.runDesign(rules, useLlm, maxIterations, mockMode, mockScenario, onProgress);
    
    setStreamProgress(null);
    setLoading(false);

    if (res.ok) {
      setActiveDesign(res.data);
      setActiveTab('overview');
      setToastMessage({ success: `Design process completed! Status: ${res.data.status}` });
      setActiveDesignId(res.data.id); // Highlight the newly run design!
      
      // Reload history list since a new design was added (or simulated)
      if (mockMode) {
        // Mock: Append a new run to history
        const newRun = {
          id: res.data.id,
          timestamp: res.data.created_at || new Date().toISOString(),
          status: res.data.status,
          competition_rules: rules,
          design: res.data.design
        };
        setHistoryList((prev) => [newRun, ...prev]);
      } else {
        loadHistory();
      }
    } else {
      // 400/422/500 errors
      setToastMessage({ error: res.data });
      // If we failed, let's keep the previous design or clear it if it was raw failure
      if (res.status === 422) {
        // Show empty design or trace if it failed validation completely
        setActiveDesign(null);
      }
    }
  };

  const handleSelectDesign = async (id) => {
    if (loading) return;
    setLoading(true);
    setToastMessage(null);
    setActiveDesignId(id);

    const res = await api.getDesignById(id, mockMode);
    setLoading(false);

    if (res.ok) {
      setActiveDesign(res.data);
      setActiveTab('overview');
      setToastMessage({ success: `Loaded design ${id} successfully.` });
      
      // Fix: Scenario dropdown must reflect the actual status of a loaded history entry, not stay stuck on last-selected value.
      if (res.data.status) {
        setMockScenario(res.data.status);
      }
    } else {
      setToastMessage({ error: res.data });
      setActiveDesign(null); // Clear active design details on failure
      setActiveDesignId(null); // De-select the failed design in sidebar
    }
  };

  const handleNewDesign = () => {
    if (loading) return;
    setActiveDesign(null);
    setActiveDesignId(null);
    setToastMessage(null);
    setActiveTab('overview');
  };

  return (
    <div className="app-container">
      {/* Sidebar containing design history */}
      <HistorySidebar
        historyList={historyList}
        activeDesignId={activeDesignId}
        onSelectDesign={handleSelectDesign}
        onNewDesign={handleNewDesign}
        historyLoading={historyLoading}
      />

      <div className="main-content">
        <Header
          mockMode={mockMode}
          setMockMode={setMockMode}
          mockScenario={mockScenario}
          setMockScenario={setMockScenario}
        />

        <div className="dashboard-grid">
          {/* Left panel: parameters inputs form */}
          <div style={{ position: 'sticky', top: '5.5rem' }}>
            <DesignForm onSubmit={handleRunDesign} loading={loading} />
          </div>

          {/* Right panel: results display with tabs */}
          <div className="glass-card" style={{ minHeight: '500px' }}>
            {streamProgress ? (
              <LiveProgressTracker progress={streamProgress} />
            ) : activeDesign ? (
              <>
                <nav className="tabs-nav">
                  <button
                    className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                  >
                    Design Overview
                  </button>
                  <button
                    className={`tab-btn ${activeTab === 'trace' ? 'active' : ''}`}
                    onClick={() => setActiveTab('trace')}
                  >
                    Convergence Trace
                  </button>
                  <button
                    className={`tab-btn ${activeTab === 'airfoils' ? 'active' : ''}`}
                    onClick={() => setActiveTab('airfoils')}
                  >
                    Airfoil Details
                  </button>
                </nav>

                <div className="tab-content tab-pane-transition" key={activeTab}>
                  {activeTab === 'overview' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      {/* Active violations list displayed at top of design */}
                      <ViolationsList violations={activeDesign.violations} />
                      <DesignResults data={activeDesign} />
                    </div>
                  )}

                  {activeTab === 'trace' && (
                    <ConvergenceTrace 
                      history={activeDesign.history} 
                      rules={activeDesign.design ? { MTOW_kg: activeDesign.design.MTOW_kg } : null}
                    />
                  )}

                  {activeTab === 'airfoils' && (
                    <div className="airfoil-details-panel">
                      <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Airfoil Search & Decisions
                      </h3>
                      {activeDesign.airfoil_selection_reasoning && (
                        <div className="reasoning-text">
                          <strong>Selection Reasoning:</strong>
                          <p style={{ marginTop: '0.4rem' }}>{activeDesign.airfoil_selection_reasoning}</p>
                        </div>
                      )}
                      
                      {activeDesign.candidate_airfoils_considered && (
                        <div>
                          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                            Airfoil Candidates Considered
                          </h4>
                          <div className="airfoil-list">
                            {activeDesign.candidate_airfoils_considered.map((airfoil) => (
                              <span 
                                key={airfoil} 
                                className={`airfoil-tag ${activeDesign.design?.airfoil_id === airfoil ? 'selected' : ''}`}
                              >
                                {airfoil} {activeDesign.design?.airfoil_id === airfoil && '✓'}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-state" style={{ height: '100%', minHeight: '400px' }}>
                <div className="empty-state-icon">
                  <svg style={{ width: '64px', height: '64px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                </div>
                <h3>Awaiting Optimization Run</h3>
                <p>
                  Configure your competition rules in the left panel and click <strong>Run Optimization</strong>. 
                  The agentic loop will compute sizing, drag polars, and select the optimal airfoil.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Global notifications (toasts) for errors & successes */}
      <Toast
        error={toastMessage?.error}
        success={toastMessage?.success}
        onClose={() => setToastMessage(null)}
      />
    </div>
  );
}
