import React from 'react';

const ExecutionFlowVisualizer = ({ trace }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981'; // green
      case 'executing': return '#3b82f6'; // blue
      case 'failed': return '#ef4444'; // red
      case 'pending': return '#9ca3af'; // gray
      default: return '#9ca3af';
    }
  };

  const getStageLabel = (stage) => {
    switch (stage) {
      case 'L1_RECEIVED': return 'L1: Received';
      case 'L1_VALIDATED': return 'L1: Validated';
      case 'L2_ROUTED': return 'L2: Orchestrated';
      case 'L3_EXECUTING': return 'L3: Executing';
      case 'L3_COMPLETED': return 'L3: Completed';
      default: return stage;
    }
  };

  const getStageDescription = (stage) => {
    switch (stage) {
      case 'L1_RECEIVED': return 'Request received at L1 interface';
      case 'L1_VALIDATED': return 'Request validated by security firewall';
      case 'L2_ROUTED': return 'Request routed by orchestrator';
      case 'L3_EXECUTING': return 'Request executing in engine';
      case 'L3_COMPLETED': return 'Execution completed';
      default: return '';
    }
  };

  const calculateLatency = (steps) => {
    if (steps.length < 2) return 0;
    const start = steps[0].timestamp;
    const end = steps[steps.length - 1].timestamp;
    return end - start;
  };

  return (
    <div className="execution-flow-visualizer">
      <div className="execution-header">
        <div className="execution-id">ID: {trace.id.substring(0, 8)}...</div>
        <div className="execution-latency">Latency: {calculateLatency(trace.steps)}ms</div>
        <div className="execution-status">
          Status: {trace.steps.some(step => step.status === 'failed') ? 'Failed' : 
                  trace.steps.every(step => step.status === 'completed') ? 'Completed' : 'In Progress'}
        </div>
      </div>
      
      <div className="flow-steps">
        {trace.steps.map((step, index) => (
          <div key={index} className="flow-step">
            <div className="step-indicator" style={{ backgroundColor: getStatusColor(step.status) }}>
              {step.status === 'completed' ? '✓' : 
               step.status === 'executing' ? '↻' : 
               step.status === 'failed' ? '✗' : '○'}
            </div>
            <div className="step-info">
              <div className="step-label">{getStageLabel(step.stage)}</div>
              <div className="step-description">{getStageDescription(step.stage)}</div>
              <div className="step-timestamp">{new Date(step.timestamp).toLocaleTimeString()}</div>
            </div>
            <div className="step-line"></div>
          </div>
        ))}
      </div>

      {trace.result && trace.result.success && (
        <div className="execution-result">
          <h4>Result:</h4>
          <pre>{JSON.stringify(trace.result.data, null, 2)}</pre>
        </div>
      )}

      {trace.result && !trace.result.success && (
        <div className="execution-error">
          <h4>Error:</h4>
          <p>{trace.result.error || 'Unknown error occurred'}</p>
        </div>
      )}
    </div>
  );
};

export default ExecutionFlowVisualizer;