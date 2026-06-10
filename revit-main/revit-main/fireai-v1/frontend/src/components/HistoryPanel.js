import React, { useState, useMemo } from 'react';

const HistoryPanel = ({ requests }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAgent, setFilterAgent] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selectedRequest, setSelectedRequest] = useState(null);

  const agents = [
    { id: 'planner', name: 'Planner Agent' },
    { id: 'executor', name: 'Executor Agent' },
    { id: 'validator', name: 'Validator Agent' },
    { id: 'optimizer', name: 'Optimizer Agent' }
  ];

  const filteredAndSortedRequests = useMemo(() => {
    let filtered = requests.filter(request => {
      const matchesSearch = request.query.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesAgent = filterAgent === 'all' || request.agent === filterAgent;
      const matchesStatus = filterStatus === 'all' || request.status === filterStatus;
      
      return matchesSearch && matchesAgent && matchesStatus;
    });

    // Sort requests
    filtered.sort((a, b) => {
      let aValue, bValue;
      
      switch (sortBy) {
        case 'timestamp':
          aValue = new Date(a.timestamp);
          bValue = new Date(b.timestamp);
          break;
        case 'latency':
          aValue = a.latency || 0;
          bValue = b.latency || 0;
          break;
        case 'query':
          aValue = a.query.toLowerCase();
          bValue = b.query.toLowerCase();
          break;
        case 'agent':
          aValue = a.agent.toLowerCase();
          bValue = b.agent.toLowerCase();
          break;
        default:
          aValue = a.timestamp;
          bValue = b.timestamp;
      }

      if (typeof aValue === 'string') {
        return sortOrder === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
      } else {
        return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
      }
    });

    return filtered;
  }, [requests, searchTerm, filterAgent, filterStatus, sortBy, sortOrder]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'failed': return '#ef4444';
      case 'processing': return '#3b82f6';
      default: return '#9ca3af';
    }
  };

  const getAgentColor = (agentId) => {
    const agent = agents.find(a => a.id === agentId);
    switch (agentId) {
      case 'planner': return '#8b5cf6';
      case 'executor': return '#06b6d4';
      case 'validator': return '#10b981';
      case 'optimizer': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const formatDate = (date) => {
    return new Date(date).toLocaleString();
  };

  const formatLatency = (latency) => {
    if (!latency) return 'N/A';
    if (latency < 1000) return `${latency}ms`;
    return `${(latency / 1000).toFixed(2)}s`;
  };

  return (
    <div className="history-panel">
      <div className="history-header">
        <h2>Request History</h2>
        <div className="history-controls">
          <input
            type="text"
            placeholder="Search queries..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
          <select 
            value={filterAgent} 
            onChange={(e) => setFilterAgent(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Agents</option>
            {agents.map(agent => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
          <select 
            value={filterStatus} 
            onChange={(e) => setFilterStatus(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="processing">Processing</option>
          </select>
          <select 
            value={`${sortBy}-${sortOrder}`} 
            onChange={(e) => {
              const [field, order] = e.target.value.split('-');
              setSortBy(field);
              setSortOrder(order);
            }}
            className="filter-select"
          >
            <option value="timestamp-desc">Newest First</option>
            <option value="timestamp-asc">Oldest First</option>
            <option value="latency-desc">Slowest First</option>
            <option value="latency-asc">Fastest First</option>
            <option value="query-asc">Query A-Z</option>
            <option value="query-desc">Query Z-A</option>
          </select>
        </div>
      </div>

      <div className="history-stats">
        <div className="stat-cards">
          <div className="stat-card">
            <div className="stat-number">{requests.length}</div>
            <div className="stat-label">Total Requests</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{requests.filter(r => r.status === 'completed').length}</div>
            <div className="stat-label">Successful</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{requests.filter(r => r.status === 'failed').length}</div>
            <div className="stat-label">Failed</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{requests.length > 0 ? Math.round(requests.reduce((acc, req) => acc + (req.latency || 0), 0) / requests.length) : 0}ms</div>
            <div className="stat-label">Avg Latency</div>
          </div>
        </div>
      </div>

      <div className="history-list">
        {filteredAndSortedRequests.length === 0 ? (
          <div className="no-history">
            <p>No requests found</p>
            <small>Submit requests to see them appear here</small>
          </div>
        ) : (
          <>
            {selectedRequest ? (
              <div className="request-detail-view">
                <button 
                  className="back-button"
                  onClick={() => setSelectedRequest(null)}
                >
                  ← Back to list
                </button>
                <div className="request-detail-card">
                  <div className="detail-header">
                    <h3>Request Details</h3>
                    <div className="detail-id">ID: {selectedRequest.id}</div>
                  </div>
                  
                  <div className="detail-content">
                    <div className="detail-row">
                      <strong>Query:</strong>
                      <span>{selectedRequest.query}</span>
                    </div>
                    <div className="detail-row">
                      <strong>Agent:</strong>
                      <span style={{ color: getAgentColor(selectedRequest.agent) }}>
                        {agents.find(a => a.id === selectedRequest.agent)?.name || selectedRequest.agent}
                      </span>
                    </div>
                    <div className="detail-row">
                      <strong>Status:</strong>
                      <span style={{ color: getStatusColor(selectedRequest.status) }}>
                        {selectedRequest.status}
                      </span>
                    </div>
                    <div className="detail-row">
                      <strong>Timestamp:</strong>
                      <span>{formatDate(selectedRequest.timestamp)}</span>
                    </div>
                    <div className="detail-row">
                      <strong>Latency:</strong>
                      <span>{formatLatency(selectedRequest.latency)}</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="request-grid">
                {filteredAndSortedRequests.map(request => (
                  <div 
                    key={request.id} 
                    className="request-card"
                    onClick={() => setSelectedRequest(request)}
                  >
                    <div className="request-header">
                      <div 
                        className="agent-badge"
                        style={{ backgroundColor: getAgentColor(request.agent) }}
                      >
                        {agents.find(a => a.id === request.agent)?.name.charAt(0) || '?'}
                      </div>
                      <div className="request-time">
                        {formatDate(request.timestamp)}
                      </div>
                    </div>
                    
                    <div className="request-query">
                      {request.query.length > 100 ? `${request.query.substring(0, 100)}...` : request.query}
                    </div>
                    
                    <div className="request-footer">
                      <div 
                        className="status-badge"
                        style={{ backgroundColor: getStatusColor(request.status) }}
                      >
                        {request.status}
                      </div>
                      <div className="latency">
                        {formatLatency(request.latency)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default HistoryPanel;