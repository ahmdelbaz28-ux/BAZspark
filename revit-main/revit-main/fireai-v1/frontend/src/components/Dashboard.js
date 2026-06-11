import React, { useState, useEffect } from 'react';

const Dashboard = ({ systemStatus, activeAgents, executionTraces, requests }) => {
  const [metrics, setMetrics] = useState({
    requestCount: 0,
    activeAgents: 0,
    avgLatency: 0,
    successRate: 0,
    errorRate: 0,
    systemUptime: '99.9%'
  });

  const [recentTraces, setRecentTraces] = useState([]);
  const [topAgents, setTopAgents] = useState([]);

  useEffect(() => {
    // Calculate metrics
    const requestCount = requests.length;
    const completedRequests = requests.filter(r => r.status === 'completed').length;
    const failedRequests = requests.filter(r => r.status === 'failed').length;
    const totalLatency = requests.reduce((acc, req) => acc + (req.latency || 0), 0);
    const avgLatency = requestCount > 0 ? Math.round(totalLatency / requestCount) : 0;
    const successRate = requestCount > 0 ? Math.round((completedRequests / requestCount) * 100) : 0;
    const errorRate = requestCount > 0 ? Math.round((failedRequests / requestCount) * 100) : 0;

    setMetrics({
      requestCount,
      activeAgents: activeAgents.length,
      avgLatency,
      successRate,
      errorRate,
      systemUptime: '99.9%'
    });

    // Get recent traces
    setRecentTraces(executionTraces.slice(-5).reverse());

    // Calculate top agents by usage
    const agentUsage = {};
    requests.forEach(req => {
      agentUsage[req.agent] = (agentUsage[req.agent] || 0) + 1;
    });

    const sortedAgents = Object.entries(agentUsage)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5);

    setTopAgents(sortedAgents);
  }, [requests, activeAgents, executionTraces]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'operational': return '#10b981';
      case 'degraded': return '#f59e0b';
      case 'down': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getLoadColor = (load) => {
    if (load < 0.3) return '#10b981';
    if (load < 0.7) return '#f59e0b';
    return '#ef4444';
  };

  const getSuccessRateColor = (rate) => {
    if (rate >= 95) return '#10b981';
    if (rate >= 80) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>System Dashboard</h2>
        <div className="system-status">
          <span className="status-indicator" style={{ backgroundColor: getStatusColor(systemStatus) }}>
            {systemStatus.charAt(0).toUpperCase() + systemStatus.slice(1)}
          </span>
          <span className="uptime">Uptime: {metrics.systemUptime}</span>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card primary">
          <div className="metric-icon">📈</div>
          <div className="metric-content">
            <div className="metric-value">{metrics.requestCount}</div>
            <div className="metric-label">Total Requests</div>
          </div>
        </div>
        
        <div className="metric-card secondary">
          <div className="metric-icon">🤖</div>
          <div className="metric-content">
            <div className="metric-value">{metrics.activeAgents}</div>
            <div className="metric-label">Active Agents</div>
          </div>
        </div>
        
        <div className="metric-card secondary">
          <div className="metric-icon">⚡</div>
          <div className="metric-content">
            <div className="metric-value">{metrics.avgLatency}ms</div>
            <div className="metric-label">Avg Latency</div>
          </div>
        </div>
        
        <div className="metric-card success">
          <div className="metric-icon">✅</div>
          <div className="metric-content">
            <div className="metric-value" style={{ color: getSuccessRateColor(metrics.successRate) }}>
              {metrics.successRate}%
            </div>
            <div className="metric-label">Success Rate</div>
          </div>
        </div>
        
        <div className="metric-card danger">
          <div className="metric-icon">❌</div>
          <div className="metric-content">
            <div className="metric-value">{metrics.errorRate}%</div>
            <div className="metric-label">Error Rate</div>
          </div>
        </div>
        
        <div className="metric-card info">
          <div className="metric-icon">⏱️</div>
          <div className="metric-content">
            <div className="metric-value">{metrics.systemUptime}</div>
            <div className="metric-label">System Uptime</div>
          </div>
        </div>
      </div>

      <div className="dashboard-content">
        <div className="dashboard-column">
          <div className="card">
            <h3>Active Agents</h3>
            <div className="agents-list">
              {activeAgents.map(agent => (
                <div key={agent.id} className="agent-item">
                  <div className="agent-info">
                    <div className="agent-name">{agent.name}</div>
                    <div className="agent-id">ID: {agent.id}</div>
                  </div>
                  <div className="agent-stats">
                    <div className="agent-load">
                      Load: <span style={{ color: getLoadColor(agent.load) }}>{(agent.load * 100).toFixed(1)}%</span>
                    </div>
                    <div className="agent-status">
                      <span 
                        className="status-dot" 
                        style={{ backgroundColor: agent.status === 'ready' ? '#10b981' : '#f59e0b' }}
                      ></span>
                      {agent.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3>Top Agents by Usage</h3>
            <div className="top-agents-list">
              {topAgents.length > 0 ? (
                topAgents.map(([agentId, count]) => {
                  const agent = activeAgents.find(a => a.id === agentId);
                  return (
                    <div key={agentId} className="top-agent-item">
                      <div className="agent-name">
                        {agent?.name || agentId}
                      </div>
                      <div className="agent-count">
                        {count} requests
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="no-data">No usage data available</p>
              )}
            </div>
          </div>
        </div>

        <div className="dashboard-column">
          <div className="card">
            <h3>Recent Executions</h3>
            <div className="recent-executions">
              {recentTraces.length > 0 ? (
                recentTraces.map(trace => {
                  const isCompleted = trace.steps.every(step => step.status === 'completed');
                  const hasErrors = trace.steps.some(step => step.status === 'failed');
                  const latency = trace.steps.length > 1 ? 
                    (trace.steps[trace.steps.length - 1].timestamp - trace.steps[0].timestamp) : 0;

                  return (
                    <div key={trace.id} className="execution-item">
                      <div className="execution-info">
                        <div className="execution-id">ID: {trace.id.substring(0, 8)}...</div>
                        <div className="execution-method">{trace.request?.method || 'Unknown'}</div>
                      </div>
                      <div className="execution-stats">
                        <div className="execution-latency">{latency}ms</div>
                        <div className={`execution-status ${isCompleted ? 'success' : hasErrors ? 'error' : 'in-progress'}`}>
                          {isCompleted ? '✅' : hasErrors ? '❌' : '🔄'}
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="no-data">No recent executions</p>
              )}
            </div>
          </div>

          <div className="card">
            <h3>System Health</h3>
            <div className="health-metrics">
              <div className="health-item">
                <div className="health-label">CPU Usage</div>
                <div className="health-bar">
                  <div 
                    className="health-fill" 
                    style={{ width: '45%', backgroundColor: '#10b981' }}
                  ></div>
                </div>
                <div className="health-value">45%</div>
              </div>
              <div className="health-item">
                <div className="health-label">Memory Usage</div>
                <div className="health-bar">
                  <div 
                    className="health-fill" 
                    style={{ width: '62%', backgroundColor: '#f59e0b' }}
                  ></div>
                </div>
                <div className="health-value">62%</div>
              </div>
              <div className="health-item">
                <div className="health-label">Disk Usage</div>
                <div className="health-bar">
                  <div 
                    className="health-fill" 
                    style={{ width: '31%', backgroundColor: '#10b981' }}
                  ></div>
                </div>
                <div className="health-value">31%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;