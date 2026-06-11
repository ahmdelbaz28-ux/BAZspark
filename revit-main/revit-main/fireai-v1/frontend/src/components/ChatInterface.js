import React, { useState, useRef, useEffect } from 'react';
import ExecutionFlowVisualizer from './ExecutionFlowVisualizer';

const ChatInterface = ({ executionTraces, setExecutionTraces, requests, setRequests }) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('executor');
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'system',
      content: 'Welcome to FireAI v1.0! I\'m ready to assist with your engineering calculations.',
      timestamp: new Date()
    }
  ]);
  const messagesEndRef = useRef(null);

  const agents = [
    { id: 'planner', name: 'Planner Agent', description: 'Creates execution plans' },
    { id: 'executor', name: 'Executor Agent', description: 'Performs calculations' },
    { id: 'validator', name: 'Validator Agent', description: 'Validates results' },
    { id: 'optimizer', name: 'Optimizer Agent', description: 'Optimizes parameters' }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // Add user message
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: input,
      timestamp: new Date(),
      agent: selectedAgent
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Simulate API call to FACP backend
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Create a simulated FACP request
      const requestId = `req_${Date.now()}`;
      const facpRequest = {
        protocol: "FACP/1.1",
        type: "request",
        id: requestId,
        timestamp: Date.now(),
        source: "client",
        target: "engine",
        execution_state: "RECEIVED",
        method: "engine.calculate",
        params: {
          task: "engineering_calculation",
          payload: { query: input },
          context: { agent: selectedAgent }
        },
        security: {
          auth_token: "simulated_token",
          permissions: ["engine_access", "execute"],
          risk_level: "low",
          idempotency_key: `idemp_${Date.now()}`
        },
        constraints: {
          timeout_ms: 8000,
          max_memory_mb: 512,
          max_recursion_depth: 5
        }
      };

      // Simulate execution flow
      const executionTrace = {
        id: requestId,
        request: facpRequest,
        startTime: Date.now(),
        steps: [
          { stage: 'L1_RECEIVED', timestamp: Date.now(), status: 'completed' },
          { stage: 'L1_VALIDATED', timestamp: Date.now() + 50, status: 'completed' },
          { stage: 'L2_ROUTED', timestamp: Date.now() + 100, status: 'completed' },
          { stage: 'L3_EXECUTING', timestamp: Date.now() + 150, status: 'executing' }
        ]
      };

      setExecutionTraces(prev => [...prev, executionTrace]);

      // Simulate backend processing
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Update execution trace with completion
      setExecutionTraces(prev => prev.map(trace => {
        if (trace.id === requestId) {
          return {
            ...trace,
            steps: [
              ...trace.steps.slice(0, -1),
              { stage: 'L3_EXECUTING', timestamp: Date.now() - 50, status: 'completed' },
              { stage: 'L3_COMPLETED', timestamp: Date.now(), status: 'completed' }
            ],
            endTime: Date.now(),
            result: {
              success: true,
              data: `Calculated result for: "${input}" using ${agents.find(a => a.id === selectedAgent)?.name}`,
              latency: 2050
            }
          };
        }
        return trace;
      }));

      // Add AI response
      const aiMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: `I processed your request using the ${agents.find(a => a.id === selectedAgent)?.name}. Result: Calculated engineering parameters for "${input}".`,
        timestamp: new Date(),
        agent: selectedAgent,
        executionId: requestId
      };

      setMessages(prev => [...prev, aiMessage]);
      
      // Add to requests history
      setRequests(prev => [...prev, {
        id: requestId,
        query: input,
        agent: selectedAgent,
        timestamp: new Date(),
        status: 'completed',
        latency: 2050
      }]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        error: error.message
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.type}`}>
              <div className="message-header">
                <span className="message-type">
                  {message.type === 'user' && '👤 You'}
                  {message.type === 'ai' && `🤖 ${agents.find(a => a.id === message.agent)?.name || 'AI Assistant'}`}
                  {message.type === 'system' && 'ℹ️ System'}
                  {message.type === 'error' && '❌ Error'}
                </span>
                <span className="message-time">
                  {message.timestamp.toLocaleTimeString()}
                </span>
              </div>
              <div className="message-content">
                {message.content}
                {message.executionId && (
                  <div className="execution-info">
                    <small>Execution ID: {message.executionId}</small>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message ai">
              <div className="message-header">
                <span className="message-type">🤖 AI Assistant</span>
                <span className="message-time">{new Date().toLocaleTimeString()}</span>
              </div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="chat-input-form">
          <div className="agent-selector">
            <label htmlFor="agent-select">Agent:</label>
            <select 
              id="agent-select" 
              value={selectedAgent} 
              onChange={(e) => setSelectedAgent(e.target.value)}
              disabled={isLoading}
            >
              {agents.map(agent => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="input-container">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me about engineering calculations, design parameters, or system optimizations..."
              rows="3"
              disabled={isLoading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <button 
              type="submit" 
              disabled={!input.trim() || isLoading}
              className="send-button"
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>

      <div className="execution-visualizer">
        <h3>Execution Flow</h3>
        {executionTraces.slice(-1).map(trace => (
          <ExecutionFlowVisualizer key={trace.id} trace={trace} />
        ))}
        {executionTraces.length === 0 && (
          <div className="no-execution">
            <p>No execution in progress</p>
            <small>Submit a request to see the execution flow visualization</small>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInterface;