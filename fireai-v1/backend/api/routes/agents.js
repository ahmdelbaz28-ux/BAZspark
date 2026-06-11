/**
 * Agent Routes for FireAI v1.0
 * API endpoints for agent management and operations
 */

const { body, validationResult, query, param } = require('express-validator');

module.exports = (app, agentService) => {
  /**
   * Get all agents
   */
  app.get('/api/agents', (req, res) => {
    try {
      const agents = agentService.getAllAgents();
      
      res.json({
        success: true,
        count: agents.length,
        agents
      });
    } catch (error) {
      console.error('Error fetching agents:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get agent by ID
   */
  app.get('/api/agents/:id', [
    param('id').notEmpty().withMessage('Agent ID is required')
  ], (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const { id } = req.params;
      const agent = agentService.getAgentById(id);

      if (!agent) {
        return res.status(404).json({
          error: 'Agent not found'
        });
      }

      res.json({
        success: true,
        agent
      });
    } catch (error) {
      console.error('Error fetching agent:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Assign task to an agent
   */
  app.post('/api/agents/:id/task', [
    param('id').notEmpty().withMessage('Agent ID is required'),
    body('task').isObject().withMessage('Task must be an object'),
    body('task.id').optional().isString().withMessage('Task ID must be a string'),
    body('task.type').optional().isString().withMessage('Task type must be a string'),
    body('task.description').optional().isString().withMessage('Task description must be a string')
  ], async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const { id } = req.params;
      const { task } = req.body;

      const result = await agentService.assignTask(id, task);

      if (result.success) {
        res.json({
          success: true,
          result: result.result,
          agentId: result.agentId,
          taskId: result.taskId,
          processingTime: result.processingTime
        });
      } else {
        res.status(400).json({
          success: false,
          error: result.error,
          agentId: result.agentId,
          taskId: result.taskId
        });
      }
    } catch (error) {
      console.error('Error assigning task to agent:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Update agent status
   */
  app.put('/api/agents/:id/status', [
    param('id').notEmpty().withMessage('Agent ID is required'),
    body('status').isIn(['ready', 'busy', 'degraded', 'maintenance']).withMessage('Invalid status')
  ], (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const { id } = req.params;
      const { status } = req.body;

      const success = agentService.updateAgentStatus(id, status);

      if (success) {
        res.json({
          success: true,
          message: `Agent ${id} status updated to ${status}`,
          agentId: id,
          newStatus: status
        });
      } else {
        res.status(404).json({
          success: false,
          error: 'Agent not found'
        });
      }
    } catch (error) {
      console.error('Error updating agent status:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get agent statistics
   */
  app.get('/api/agents/stats', (req, res) => {
    try {
      const stats = agentService.getAgentStats();
      
      res.json({
        success: true,
        stats,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('Error fetching agent stats:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get agent capabilities
   */
  app.get('/api/agents/:id/capabilities', [
    param('id').notEmpty().withMessage('Agent ID is required')
  ], (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const { id } = req.params;
      const agent = agentService.getAgentById(id);

      if (!agent) {
        return res.status(404).json({
          error: 'Agent not found'
        });
      }

      res.json({
        success: true,
        agentId: id,
        capabilities: agent.capabilities,
        capabilityCount: agent.capabilities.length
      });
    } catch (error) {
      console.error('Error fetching agent capabilities:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });
};