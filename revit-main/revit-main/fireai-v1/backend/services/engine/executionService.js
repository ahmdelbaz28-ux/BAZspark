/**
 * Execution Service for FireAI v1.0
 * Handles task execution and engine operations
 */

const { v4: uuidv4 } = require('uuid');

class ExecutionService {
  constructor() {
    this.executions = new Map();
    this.executionQueue = [];
    this.activeExecutions = new Set();
    this.results = new Map();
    this.config = {
      maxConcurrentExecutions: 10,
      defaultTimeout: 8000,
      maxTimeout: 30000,
      maxMemory: 1024, // MB
      maxRecursionDepth: 10
    };
  }

  /**
   * Submit a task for execution
   */
  async submitTask(task) {
    const executionId = task.id || uuidv4();
    const execution = {
      id: executionId,
      task,
      status: 'queued',
      submittedAt: new Date(),
      startedAt: null,
      completedAt: null,
      result: null,
      error: null,
      progress: 0,
      nodeId: 'L3_Engine',
      engineVersion: 'FACP/1.1'
    };

    // Add to execution queue
    this.executionQueue.push(executionId);
    this.executions.set(executionId, execution);

    // Process the queue
    this.processQueue();

    return executionId;
  }

  /**
   * Process the execution queue
   */
  async processQueue() {
    // Process queued executions up to the max concurrent limit
    while (
      this.executionQueue.length > 0 &&
      this.activeExecutions.size < this.config.maxConcurrentExecutions
    ) {
      const executionId = this.executionQueue.shift();
      if (this.executions.has(executionId) && !this.activeExecutions.has(executionId)) {
        this.activeExecutions.add(executionId);
        this.executeTask(executionId);
      }
    }
  }

  /**
   * Execute a single task
   */
  async executeTask(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution) return;

    try {
      execution.status = 'executing';
      execution.startedAt = new Date();

      // Update progress
      this.updateProgress(executionId, 10);

      // Simulate execution process
      const result = await this.performExecution(execution.task);

      execution.result = result;
      execution.status = 'completed';
      execution.completedAt = new Date();
      execution.progress = 100;

      // Store result
      this.results.set(executionId, result);

      // Clean up active execution
      this.activeExecutions.delete(executionId);

      // Process next in queue
      this.processQueue();

    } catch (error) {
      execution.error = error.message;
      execution.status = 'failed';
      execution.completedAt = new Date();
      execution.progress = 100;

      // Clean up active execution
      this.activeExecutions.delete(executionId);

      // Process next in queue
      this.processQueue();
    }
  }

  /**
   * Perform the actual execution based on task type
   */
  async performExecution(task) {
    const startTime = Date.now();
    const timeout = Math.min(task.constraints?.timeout_ms || this.config.defaultTimeout, this.config.maxTimeout);

    // Simulate different types of execution
    switch (task.method) {
      case 'engine.calculate':
        return await this.performCalculation(task.params.payload, timeout);
      case 'engine.validate':
        return await this.performValidation(task.params.payload, timeout);
      case 'engine.transform':
        return await this.performTransformation(task.params.payload, timeout);
      case 'engine.optimize':
        return await this.performOptimization(task.params.payload, timeout);
      default:
        return await this.performGenericExecution(task, timeout);
    }
  }

  /**
   * Perform calculation
   */
  async performCalculation(payload, timeout) {
    // Simulate calculation process
    await this.delay(Math.min(1000, timeout)); // Max 1 second for calculations

    if (payload.operation === 'add' && Array.isArray(payload.operands)) {
      return {
        result: payload.operands.reduce((sum, num) => sum + num, 0),
        operation: 'addition',
        operands_count: payload.operands.length,
        calculated_at: new Date().toISOString(),
        engine: 'deterministic_calculation_engine'
      };
    } else if (payload.operation === 'multiply' && Array.isArray(payload.operands)) {
      return {
        result: payload.operands.reduce((product, num) => product * num, 1),
        operation: 'multiplication',
        operands_count: payload.operands.length,
        calculated_at: new Date().toISOString(),
        engine: 'deterministic_calculation_engine'
      };
    } else if (payload.calculation_type === 'voltage_drop') {
      // Simulate electrical calculation
      const current = payload.current || 10;
      const length = payload.length || 50;
      const resistance = payload.resistance || 0.02;
      const supplyVoltage = payload.supply_voltage || 230;
      const systemType = payload.system_type || 'single_phase';

      let voltageDrop;
      if (systemType === 'three_phase') {
        voltageDrop = 1.732 * current * length * resistance;
      } else {
        voltageDrop = 2 * current * length * resistance;
      }

      const voltageDropPercentage = (voltageDrop / supplyVoltage) * 100;

      return {
        voltage_drop_volts: parseFloat(voltageDrop.toFixed(3)),
        voltage_drop_percentage: parseFloat(voltageDropPercentage.toFixed(3)),
        acceptable: voltageDropPercentage <= 3, // Standard 3% limit
        supply_voltage: supplyVoltage,
        calculated_at: new Date().toISOString(),
        engine: 'electrical_calculation_engine'
      };
    } else {
      // Generic calculation
      return {
        result: `Calculated result for: ${JSON.stringify(payload)}`,
        operation: 'generic_calculation',
        calculated_at: new Date().toISOString(),
        engine: 'generic_calculation_engine'
      };
    }
  }

  /**
   * Perform validation
   */
  async performValidation(payload, timeout) {
    // Simulate validation process
    await this.delay(Math.min(800, timeout)); // Max 800ms for validation

    // Simulate validation results
    const validationResults = {
      valid: Math.random() > 0.1, // 90% success rate
      errors: [],
      warnings: [],
      validated_at: new Date().toISOString(),
      engine: 'validation_engine'
    };

    // Add some sample errors/warnings based on payload
    if (payload.value < 0) {
      validationResults.errors.push({
        code: 'NEGATIVE_VALUE',
        message: 'Value should not be negative',
        field: 'value',
        severity: 'error'
      });
    }

    if (payload.value > 1000000) {
      validationResults.warnings.push({
        code: 'HIGH_VALUE',
        message: 'Value is unusually high',
        field: 'value',
        severity: 'warning'
      });
    }

    return validationResults;
  }

  /**
   * Perform transformation
   */
  async performTransformation(payload, timeout) {
    // Simulate transformation process
    await this.delay(Math.min(1200, timeout)); // Max 1.2 seconds for transformation

    // Simulate different types of transformations
    if (payload.type === 'format_conversion') {
      return {
        transformed: true,
        original_format: typeof payload.data,
        converted_data: JSON.stringify(payload.data),
        conversion_type: 'json_to_string',
        converted_at: new Date().toISOString(),
        engine: 'format_transformation_engine'
      };
    } else if (payload.type === 'unit_conversion') {
      const conversionFactors = {
        'm_to_cm': 100,
        'cm_to_m': 0.01,
        'kg_to_g': 1000,
        'g_to_kg': 0.001
      };

      const factor = conversionFactors[`${payload.from_unit}_to_${payload.to_unit}`];
      if (factor) {
        return {
          original_value: payload.value,
          converted_value: payload.value * factor,
          from_unit: payload.from_unit,
          to_unit: payload.to_unit,
          conversion_factor: factor,
          converted_at: new Date().toISOString(),
          engine: 'unit_conversion_engine'
        };
      }
    }

    // Default transformation
    return {
      transformed: true,
      original_data: payload,
      transformed_data: JSON.parse(JSON.stringify(payload)), // Deep clone
      transformation_applied: 'data_copy',
      transformed_at: new Date().toISOString(),
      engine: 'generic_transformation_engine'
    };
  }

  /**
   * Perform optimization
   */
  async performOptimization(payload, timeout) {
    // Simulate optimization process
    await this.delay(Math.min(2000, timeout)); // Max 2 seconds for optimization

    // Simulate optimization results
    return {
      optimized: true,
      original_parameters: payload.parameters || {},
      optimized_parameters: this.generateOptimizedParams(payload.parameters || {}),
      improvement_percentage: Math.floor(Math.random() * 20) + 5, // 5-25% improvement
      optimization_method: 'gradient_descent_simulation',
      optimized_at: new Date().toISOString(),
      engine: 'optimization_engine'
    };
  }

  /**
   * Generate optimized parameters
   */
  generateOptimizedParams(originalParams) {
    const optimized = {};
    for (const [key, value] of Object.entries(originalParams)) {
      if (typeof value === 'number') {
        // Adjust by ±10%
        const adjustment = (Math.random() - 0.5) * 0.2; // -10% to +10%
        optimized[key] = value * (1 + adjustment);
      } else {
        optimized[key] = value;
      }
    }
    return optimized;
  }

  /**
   * Perform generic execution
   */
  async performGenericExecution(task, timeout) {
    // Simulate generic execution process
    await this.delay(Math.min(1500, timeout)); // Max 1.5 seconds for generic execution

    return {
      executed: true,
      method: task.method,
      input: task.params,
      output: `Processed ${task.method} with payload: ${JSON.stringify(task.params.payload)}`,
      executed_at: new Date().toISOString(),
      engine: 'generic_execution_engine'
    };
  }

  /**
   * Update execution progress
   */
  updateProgress(executionId, progress) {
    const execution = this.executions.get(executionId);
    if (execution) {
      execution.progress = progress;
    }
  }

  /**
   * Get execution by ID
   */
  getExecution(executionId) {
    return this.executions.get(executionId);
  }

  /**
   * Get execution result by ID
   */
  getExecutionResult(executionId) {
    return this.results.get(executionId);
  }

  /**
   * Get all executions
   */
  getAllExecutions() {
    return Array.from(this.executions.values());
  }

  /**
   * Get execution queue status
   */
  getQueueStatus() {
    return {
      pending: this.executionQueue.length,
      active: this.activeExecutions.size,
      total: this.executions.size,
      max_concurrent: this.config.maxConcurrentExecutions,
      capacity_remaining: this.config.maxConcurrentExecutions - this.activeExecutions.size
    };
  }

  /**
   * Cancel execution by ID
   */
  cancelExecution(executionId) {
    // Remove from queue if not yet started
    const queueIndex = this.executionQueue.indexOf(executionId);
    if (queueIndex !== -1) {
      this.executionQueue.splice(queueIndex, 1);
      this.executions.get(executionId).status = 'cancelled';
      return true;
    }

    // If already executing, we can't cancel it easily in this simulation
    return false;
  }

  /**
   * Get execution statistics
   */
  getExecutionStats() {
    const executions = this.getAllExecutions();
    const completed = executions.filter(e => e.status === 'completed');
    const failed = executions.filter(e => e.status === 'failed');
    const queued = executions.filter(e => e.status === 'queued');
    const executing = executions.filter(e => e.status === 'executing');

    const totalLatency = completed.reduce((sum, exec) => {
      if (exec.completedAt && exec.startedAt) {
        return sum + (new Date(exec.completedAt) - new Date(exec.startedAt));
      }
      return sum;
    }, 0);

    return {
      total_executions: executions.length,
      completed_executions: completed.length,
      failed_executions: failed.length,
      queued_executions: queued.length,
      executing_executions: executing.length,
      success_rate: completed.length > 0 ? (completed.length / executions.length) * 100 : 0,
      avg_latency_ms: completed.length > 0 ? totalLatency / completed.length : 0,
      queue_length: this.executionQueue.length,
      active_executions: this.activeExecutions.size
    };
  }

  /**
   * Helper delay function
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = { ExecutionService };