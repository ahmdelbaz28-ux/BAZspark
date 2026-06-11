import React from 'react';

const Header = ({ activeTab, setActiveTab, systemStatus }) => {
  const tabs = [
    { id: 'chat', label: 'Chat', icon: '💬' },
    { id: 'agents', label: 'Agents', icon: '🤖' },
    { id: 'status', label: 'Execution', icon: '⚡' },
    { id: 'history', label: 'History', icon: '📜' },
    { id: 'dashboard', label: 'Dashboard', icon: '📊' }
  ];

  return (
    <header className="header">
      <div className="logo-section">
        <h1>🔥 FireAI v1.0</h1>
        <span className={`status-indicator ${systemStatus}`}>
          {systemStatus === 'operational' ? '●' : '●'} {systemStatus.charAt(0).toUpperCase() + systemStatus.slice(1)}
        </span>
      </div>
      
      <nav className="navigation">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`nav-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="icon">{tab.icon}</span>
            <span className="label">{tab.label}</span>
          </button>
        ))}
      </nav>
    </header>
  );
};

export default Header;