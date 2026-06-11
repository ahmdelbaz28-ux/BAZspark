import React, { useState } from 'react';
import ExecutionFlowVisualizer from './ExecutionFlowVisualizer';

const ExecutionStatus = ({ executionTraces }) => {
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');

  const getStatusCounts = () => {
    const counts = {
      all: executionTraces.length,
      completed: executionTraces.filter(trace => trace.steps.every(step => step.status === 'completed')).length,
      inProgress: executionTraces.filter(trace => trace.steps.some(step => step.status === 'executing')).length,
      failed: executionTraces.filter(trace => trace.steps.some(step => step.status === 'failed')).length
    };
    return counts;
  };

  const getFilteredTraces = () => {
    if (filterStatus === 'all') return executionTraces;
    if (filterStatus === 'completed') {
      return executionTraces.filter(trace => trace.steps.every(step => step.status === 'completed'));
    }
    if (filterStatus === 'inProgress') {
      return executionTraces.filter(trace => trace.steps.some(step => step.status === 'executing'));
    }
    if (filterStatus === 'failed') {
      return executionTraces.filter(trace => trace.steps.some(step => step.status === 'failed'));
    }
    return executionTraces;
  };

  const getTraceStatus = (trace) => {
    if (trace.steps.some(step => step.status === 'failed')) return 'failed';
    if (trace.steps.some(step => step.status === 'executing')) return 'inProgress';
    if (trace.steps.every(step => step.status === 'completed')) return 'completed';
    return 'pending';
  };

  const getTraceStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'inProgress': return '#3b82f6';
      case 'failed': return '#ef4444';
      default: return '#9ca3af';
    }
  };

  const statusCounts = getStatusCounts();
  const filteredTraces = getFilteredTraces();

  return (
    <div className="execution-status">
      <div className="status-header">
        <h2>Execution Status Dashboard</h2>
        <div className="status-filters">
          <button 
            className={`status-filter-btn ${filterStatus === 'all' ? 'active' : ''}`}
            onClick={() => setFilterStatus('all')}
          >
            All ({statusCounts.all})
          </button>
          <button 
            className={`status-filter-btn ${filterStatus === 'completed' ? 'active' : ''}`}
            onClick={() => setFilterStatus('completed')}
          >
            Completed ({statusCounts.completed})
          </button>
          <button 
            className={`status-filter-btn ${filterStatus === 'inProgress' ? 'active' : ''}`}
            onClick={() => setFilterStatus('inProgress')}
          >
            In Progress ({statusCounts.inProgress})
          </button>
          <button 
            className={`status-filter-btn ${filterStatus === 'failed' ? 'active' : ''}`}
            onClick={() => setFilterStatus('failed')}
          >
            Failed ({statusCounts.failed})
          </button>
        </div>
      </div>

      <div className="status-metrics">
        <div className="metric-cards">
          <div className="metric-card">
            <div className="metric-value">{statusCounts.completed}</div>
            <div className="metric-label">Completed</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{statusCounts.inProgress}</div>
            <div className="metric-label">In Progress</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{statusCounts.failed}</div>
            <div className="metric-label">Failed</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{executionTraces.length > 0 ? Math.round(executionTraces.reduce((acc, trace) => {
              const start = trace.steps[0].timestamp;
              const end = trace.steps[trace.steps.length - 1].timestamp;
              return acc + (end - start);
            }, 0) / executionTraces.length) : 0}ms</div>
            <div className="metric-label">Avg Latency</div>
          </div>
        </div>
      </div>

      <div className="execution-list">
        {filteredTraces.length === 0 ? (
          <div className="no-executions">
            <p>No executions found</p>
            <small>Submit a request to see execution traces</small>
          </div>
        ) : (
          <>
            {selectedTrace ? (
              <div className="execution-detail-view">
                <button 
                  className="back-button"
                  onClick={() => setSelectedTrace(null)}
                >
                  ← Back to list
                </button>
                <ExecutionFlowVisualizer trace={selectedTrace} />
              </div>
            ) : (
              <div className="execution-traces-grid">
                {filteredTraces.slice(0, 20).map((trace) => {
                  const traceStatus = getTraceStatus(trace);
                  const latency = trace.steps.length > 1 ? 
                    (trace.steps[trace.steps.length - 1].timestamp - trace.steps[0].timestamp) : 0;
                  
                  return (
                    <div 
                      key={trace.id} 
                      className="execution-trace-card"
                      onClick={() => setSelectedTrace(trace)}
                    >
                      <div className="trace-header">
                        <div className="trace-id">ID: {trace.id.substring(0, 8)}...</div>
                        <div 
                          className="trace-status-badge"
                          style={{ backgroundColor: getTraceStatusColor(traceStatus) }}
                        >
                          {traceStatus.replace(/([A-Z])/g, ' $1').trim()}
                        </div>
                      </div>
                      
                      <div className="trace-details">
                        <div className="trace-method">{trace.request?.method || 'Unknown'}</div>
                        <div className="trace-latency">{latency}ms</div>
                      </div>
                      
                      <div className="trace-summary">
                        <div className="trace-steps">
                          {trace.steps.slice(0, 3).map((step, idx) => (
                            <span key={idx} className="step-chip">
                              {step.stage.split('_')[1]}
                            </span>
                          ))}
                          {trace.steps.length > 3 && (
                            <span className="step-chip">+{trace.steps.length - 3}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ExecutionStatus;