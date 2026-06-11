import React, { useState, useEffect } from 'react';
import './styles/App.css';
import ChatInterface from './components/ChatInterface';
import AgentPanel from './components/AgentPanel';
import ExecutionStatus from './components/ExecutionStatus';
import HistoryPanel from './components/HistoryPanel';
import Dashboard from './components/Dashboard';
import Header from './components/Header';

function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [systemStatus, setSystemStatus] = useState('operational');
  const [activeAgents, setActiveAgents] = useState([]);
  const [executionTraces, setExecutionTraces] = useState([]);
  const [requests, setRequests] = useState([]);

  // Simulate connecting to backend
  useEffect(() => {
    // In a real implementation, this would connect to the FACP backend
    console.log('Connecting to FACP backend...');
    
    // Simulate getting system status
    setSystemStatus('operational');
    setActiveAgents([
      { id: 'planner', name: 'Planner Agent', status: 'ready', load: 0.3 },
      { id: 'executor', name: 'Executor Agent', status: 'ready', load: 0.1 },
      { id: 'validator', name: 'Validator Agent', status: 'ready', load: 0.05 },
      { id: 'optimizer', name: 'Optimizer Agent', status: 'busy', load: 0.8 }
    ]);
  }, []);

  const renderActiveTab = () => {
    switch(activeTab) {
      case 'chat':
        return <ChatInterface 
          executionTraces={executionTraces} 
          setExecutionTraces={setExecutionTraces}
          requests={requests}
          setRequests={setRequests}
        />;
      case 'agents':
        return <AgentPanel activeAgents={activeAgents} />;
      case 'status':
        return <ExecutionStatus executionTraces={executionTraces} />;
      case 'history':
        return <HistoryPanel requests={requests} />;
      case 'dashboard':
        return <Dashboard 
          systemStatus={systemStatus} 
          activeAgents={activeAgents} 
          executionTraces={executionTraces}
          requests={requests}
        />;
      default:
        return <ChatInterface 
          executionTraces={executionTraces} 
          setExecutionTraces={setExecutionTraces}
          requests={requests}
          setRequests={setRequests}
        />;
    }
  };

  return (
    <div className="App">
      <Header 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        systemStatus={systemStatus} 
      />
      
      <main className="main-content">
        {renderActiveTab()}
      </main>
    </div>
  );
}

export default App;