import React from 'react';

const AgentPanel = ({ activeAgents }) => {
  const agentCapabilities = {
    planner: ['Task planning', 'Workflow design', 'Resource allocation', 'Schedule optimization'],
    executor: ['Calculations', 'Simulations', 'Data processing', 'Model execution'],
    validator: ['Verification', 'Quality checks', 'Compliance validation', 'Error detection'],
    optimizer: ['Parameter tuning', 'Performance optimization', 'Efficiency improvement', 'Cost reduction']
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'ready': return '#10b981';
      case 'busy': return '#f59e0b';
      case 'maintenance': return '#6b7280';
      case 'error': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getLoadColor = (load) => {
    if (load < 0.3) return '#10b981'; // green
    if (load < 0.7) return '#f59e0b'; // yellow
    return '#ef4444'; // red
  };

  return (
    <div className="agent-panel">
      <h2>AI Agents Dashboard</h2>
      <div className="agent-grid">
        {activeAgents.map((agent) => (
          <div key={agent.id} className="agent-card">
            <div className="agent-header">
              <div className="agent-icon">🤖</div>
              <div className="agent-info">
                <h3>{agent.name}</h3>
                <div className="agent-id">ID: {agent.id}</div>
              </div>
              <div 
                className="agent-status-indicator" 
                style={{ backgroundColor: getStatusColor(agent.status) }}
              >
                {agent.status.toUpperCase()}
              </div>
            </div>

            <div className="agent-stats">
              <div className="stat-item">
                <span className="stat-label">Load:</span>
                <span 
                  className="stat-value load-value" 
                  style={{ color: getLoadColor(agent.load) }}
                >
                  {(agent.load * 100).toFixed(1)}%
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Status:</span>
                <span className="stat-value">{agent.status}</span>
              </div>
            </div>

            <div className="agent-capabilities">
              <h4>Capabilities:</h4>
              <ul>
                {agentCapabilities[agent.id]?.map((capability, idx) => (
                  <li key={idx}>{capability}</li>
                )) || <li>No capabilities defined</li>}
              </ul>
            </div>

            <div className="agent-actions">
              <button className="btn btn-secondary" disabled={agent.status !== 'ready'}>
                Configure
              </button>
              <button className="btn btn-primary">
                {agent.status === 'ready' ? 'Activate' : agent.status === 'busy' ? 'Monitor' : 'Restart'}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="agent-metrics">
        <h3>System Metrics</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value">{activeAgents.length}</div>
            <div className="metric-label">Active Agents</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {activeAgents.filter(a => a.status === 'ready').length}
            </div>
            <div className="metric-label">Ready</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {activeAgents.filter(a => a.status === 'busy').length}
            </div>
            <div className="metric-label">Busy</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">
              {Math.round(activeAgents.reduce((acc, agent) => acc + agent.load, 0) / activeAgents.length * 100) || 0}%
            </div>
            <div className="metric-label">Avg Load</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentPanel;