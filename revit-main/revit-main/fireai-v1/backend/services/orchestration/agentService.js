/**
 * Agent Service for FireAI v1.0
 * Manages AI agents and their lifecycle
 */

const { v4: uuidv4 } = require('uuid');

class AgentService {
  constructor() {
    this.agents = new Map();
    this.agentTypes = [
      {
        id: 'planner',
        name: 'Planner Agent',
        description: 'Creates execution plans and coordinates workflows',
        capabilities: ['task_planning', 'workflow_design', 'resource_allocation', 'schedule_optimization'],
        status: 'ready',
        load: 0.0
      },
      {
        id: 'executor',
        name: 'Executor Agent',
        description: 'Performs calculations and executes tasks',
        capabilities: ['calculations', 'simulations', 'data_processing', 'model_execution'],
        status: 'ready',
        load: 0.0
      },
      {
        id: 'validator',
        name: 'Validator Agent',
        description: 'Validates results and ensures quality',
        capabilities: ['verification', 'quality_checks', 'compliance_validation', 'error_detection'],
        status: 'ready',
        load: 0.0
      },
      {
        id: 'optimizer',
        name: 'Optimizer Agent',
        description: 'Optimizes parameters and improves performance',
        capabilities: ['parameter_tuning', 'performance_optimization', 'efficiency_improvement', 'cost_reduction'],
        status: 'ready',
        load: 0.0
      }
    ];

    // Initialize agents
    this.agentTypes.forEach(agentType => {
      this.agents.set(agentType.id, {
        ...agentType,
        id: agentType.id,
        instanceId: uuidv4(),
        createdAt: new Date(),
        lastActive: new Date(),
        totalTasks: 0,
        successfulTasks: 0,
        failedTasks: 0,
        avgLatency: 0,
        config: {
          maxConcurrentTasks: 5,
          timeoutMs: 30000,
          memoryLimit: '512MB',
          retryAttempts: 3
        }
      });
    });
  }

  /**
   * Get all agents
   */
  getAllAgents() {
    return Array.from(this.agents.values()).map(agent => ({
      id: agent.id,
      name: agent.name,
      description: agent.description,
      status: agent.status,
      load: agent.load,
      capabilities: agent.capabilities,
      totalTasks: agent.totalTasks,
      successfulTasks: agent.successfulTasks,
      failedTasks: agent.failedTasks,
      avgLatency: agent.avgLatency,
      lastActive: agent.lastActive
    }));
  }

  /**
   * Get agent by ID
   */
  getAgentById(agentId) {
    const agent = this.agents.get(agentId);
    if (!agent) return null;

    return {
      id: agent.id,
      name: agent.name,
      description: agent.description,
      status: agent.status,
      load: agent.load,
      capabilities: agent.capabilities,
      totalTasks: agent.totalTasks,
      successfulTasks: agent.successfulTasks,
      failedTasks: agent.failedTasks,
      avgLatency: agent.avgLatency,
      lastActive: agent.lastActive,
      config: agent.config,
      instanceId: agent.instanceId,
      createdAt: agent.createdAt
    };
  }

  /**
   * Assign task to an agent
   */
  async assignTask(agentId, task) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent with ID ${agentId} not found`);
    }

    if (agent.status !== 'ready') {
      throw new Error(`Agent ${agentId} is not ready, current status: ${agent.status}`);
    }

    // Update agent stats
    agent.totalTasks++;
    agent.lastActive = new Date();

    // Increase load temporarily during processing
    agent.load = Math.min(1.0, agent.load + 0.2);

    try {
      // Simulate task processing
      const result = await this.processTask(agent, task);

      // Update success stats
      agent.successfulTasks++;
      agent.avgLatency = this.calculateNewAvgLatency(
        agent.avgLatency,
        agent.successfulTasks - 1,
        result.processingTime
      );

      return {
        success: true,
        result,
        agentId,
        taskId: task.id || uuidv4(),
        processingTime: result.processingTime
      };
    } catch (error) {
      // Update failure stats
      agent.failedTasks++;
      agent.status = 'degraded'; // Mark as degraded on failure
      
      return {
        success: false,
        error: error.message,
        agentId,
        taskId: task.id || uuidv4()
      };
    } finally {
      // Decrease load after processing
      agent.load = Math.max(0, agent.load - 0.2);
      
      // If agent was marked as degraded and has no failures recently, restore to ready
      if (agent.status === 'degraded' && agent.failedTasks < agent.totalTasks * 0.1) {
        agent.status = 'ready';
      }
    }
  }

  /**
   * Process a task by an agent
   */
  async processTask(agent, task) {
    const startTime = Date.now();

    // Simulate processing based on agent type
    await this.delay(this.calculateProcessingTime(agent, task));

    const processingTime = Date.now() - startTime;

    return {
      data: this.generateAgentOutput(agent, task),
      processingTime,
      agentId: agent.id,
      taskId: task.id || uuidv4(),
      completedAt: new Date()
    };
  }

  /**
   * Calculate processing time based on agent and task
   */
  calculateProcessingTime(agent, task) {
    // Base time depends on agent type
    let baseTime = 500; // 500ms base time
    
    switch (agent.id) {
      case 'planner':
        baseTime = 800;
        break;
      case 'executor':
        baseTime = 600;
        break;
      case 'validator':
        baseTime = 400;
        break;
      case 'optimizer':
        baseTime = 1000;
        break;
    }

    // Adjust based on complexity (if provided)
    const complexity = task.complexity || 1;
    return Math.round(baseTime * complexity * (1 + agent.load));
  }

  /**
   * Generate output based on agent type and task
   */
  generateAgentOutput(agent, task) {
    const baseOutput = {
      agentId: agent.id,
      agentName: agent.name,
      taskId: task.id || uuidv4(),
      processedAt: new Date().toISOString(),
      input: task
    };

    switch (agent.id) {
      case 'planner':
        return {
          ...baseOutput,
          type: 'plan',
          plan: {
            steps: this.generatePlanSteps(task),
            estimatedDuration: this.estimateDuration(task),
            requiredResources: this.estimateResources(task)
          }
        };
      case 'executor':
        return {
          ...baseOutput,
          type: 'execution_result',
          result: this.executeTask(task),
          metrics: this.calculateMetrics(task)
        };
      case 'validator':
        return {
          ...baseOutput,
          type: 'validation_result',
          isValid: this.validateResult(task),
          issues: this.identifyIssues(task),
          confidence: this.calculateConfidence(task)
        };
      case 'optimizer':
        return {
          ...baseOutput,
          type: 'optimization_result',
          optimizedParams: this.optimizeParameters(task),
          improvementPercentage: this.calculateImprovement(task)
        };
      default:
        return {
          ...baseOutput,
          type: 'generic_result',
          result: `Processed by ${agent.name}: ${JSON.stringify(task)}`
        };
    }
  }

  /**
   * Generate plan steps for planner agent
   */
  generatePlanSteps(task) {
    return [
      { step: 'analyze_requirements', status: 'completed', duration: 150 },
      { step: 'identify_resources', status: 'completed', duration: 100 },
      { step: 'create_timeline', status: 'completed', duration: 200 },
      { step: 'allocate_budget', status: 'completed', duration: 100 }
    ];
  }

  /**
   * Estimate duration for planner agent
   */
  estimateDuration(task) {
    return Math.floor(Math.random() * 3600) + 1800; // Random duration between 30-90 minutes
  }

  /**
   * Estimate resources for planner agent
   */
  estimateResources(task) {
    return {
      human_resources: Math.floor(Math.random() * 5) + 1,
      computational_resources: 'Medium',
      budget: Math.floor(Math.random() * 10000) + 5000
    };
  }

  /**
   * Execute task for executor agent
   */
  executeTask(task) {
    // Simulate different types of execution based on task
    if (task.type === 'calculation') {
      return {
        result: Math.random() * 1000,
        units: task.units || 'dimensionless',
        accuracy: 'high'
      };
    } else if (task.type === 'simulation') {
      return {
        result: { temperature: 25.5, pressure: 1.013, flow_rate: 10.2 },
        time_series: Array.from({ length: 10 }, (_, i) => ({
          time: i * 10,
          value: Math.sin(i / 2) * 100
        })),
        convergence: true
      };
    } else {
      return {
        result: `Executed task: ${task.description || JSON.stringify(task)}`,
        status: 'completed'
      };
    }
  }

  /**
   * Calculate metrics for executor agent
   */
  calculateMetrics(task) {
    return {
      execution_time: Math.floor(Math.random() * 500) + 100,
      memory_used: Math.floor(Math.random() * 512) + 64,
      accuracy: 99.5
    };
  }

  /**
   * Validate result for validator agent
   */
  validateResult(task) {
    // Simulate validation result
    return Math.random() > 0.1; // 90% pass rate
  }

  /**
   * Identify issues for validator agent
   */
  identifyIssues(task) {
    const issues = [];
    if (Math.random() > 0.8) {
      issues.push({
        type: 'accuracy',
        severity: 'low',
        description: 'Minor deviation detected in calculation'
      });
    }
    return issues;
  }

  /**
   * Calculate confidence for validator agent
   */
  calculateConfidence(task) {
    return Math.floor(Math.random() * 15) + 85; // 85-100%
  }

  /**
   * Optimize parameters for optimizer agent
   */
  optimizeParameters(task) {
    return {
      original_values: task.parameters || { param1: 10, param2: 20 },
      optimized_values: { 
        param1: Math.random() * 5 + 8, 
        param2: Math.random() * 10 + 15 
      },
      constraints: task.constraints || {}
    };
  }

  /**
   * Calculate improvement for optimizer agent
   */
  calculateImprovement(task) {
    return Math.floor(Math.random() * 20) + 5; // 5-25% improvement
  }

  /**
   * Calculate new average latency
   */
  calculateNewAvgLatency(currentAvg, count, newValue) {
    if (count === 0) return newValue;
    return (currentAvg * count + newValue) / (count + 1);
  }

  /**
   * Update agent status
   */
  updateAgentStatus(agentId, status) {
    const agent = this.agents.get(agentId);
    if (!agent) return false;

    agent.status = status;
    agent.lastActive = new Date();
    return true;
  }

  /**
   * Get agent statistics
   */
  getAgentStats() {
    const agents = this.getAllAgents();
    return {
      total_agents: agents.length,
      ready_agents: agents.filter(a => a.status === 'ready').length,
      busy_agents: agents.filter(a => a.status === 'busy').length,
      degraded_agents: agents.filter(a => a.status === 'degraded').length,
      avg_load: agents.reduce((sum, agent) => sum + agent.load, 0) / agents.length,
      total_tasks: agents.reduce((sum, agent) => sum + agent.totalTasks, 0),
      successful_tasks: agents.reduce((sum, agent) => sum + agent.successfulTasks, 0),
      failed_tasks: agents.reduce((sum, agent) => sum + agent.failedTasks, 0)
    };
  }

  /**
   * Helper delay function
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = { AgentService };