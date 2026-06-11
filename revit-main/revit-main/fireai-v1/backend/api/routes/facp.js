/**
 * FACP Routes for FireAI v1.0
 * API endpoints for FACP protocol operations
 */

const { body, validationResult, query } = require('express-validator');

module.exports = (app, facpService, io) => {
  /**
   * Submit a FACP request
   */
  app.post('/api/facp/request', [
    body('protocol').notEmpty().withMessage('Protocol is required'),
    body('id').notEmpty().withMessage('Request ID is required'),
    body('method').notEmpty().withMessage('Method is required'),
    body('params').isObject().withMessage('Params must be an object'),
    body('security').isObject().withMessage('Security block is required')
  ], async (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const request = req.body;
      const response = await facpService.processRequest(request, io);

      res.json(response);
    } catch (error) {
      console.error('Error processing FACP request:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get execution traces
   */
  app.get('/api/facp/executions', [
    query('limit').optional().isInt({ min: 1, max: 100 }).withMessage('Limit must be between 1 and 100')
  ], (req, res) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({
          error: 'Validation failed',
          details: errors.array()
        });
      }

      const limit = parseInt(req.query.limit) || 20;
      const traces = facpService.getExecutionTraces(limit);

      res.json({
        success: true,
        count: traces.length,
        traces
      });
    } catch (error) {
      console.error('Error fetching execution traces:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get execution trace by ID
   */
  app.get('/api/facp/executions/:id', (req, res) => {
    try {
      const { id } = req.params;
      const trace = facpService.getExecutionTraceById(id);

      if (!trace) {
        return res.status(404).json({
          error: 'Execution trace not found'
        });
      }

      res.json({
        success: true,
        trace
      });
    } catch (error) {
      console.error('Error fetching execution trace:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get system metrics
   */
  app.get('/api/facp/metrics', (req, res) => {
    try {
      const metrics = facpService.getSystemMetrics();
      
      res.json({
        success: true,
        metrics,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('Error fetching system metrics:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Health check endpoint
   */
  app.get('/api/facp/health', (req, res) => {
    try {
      const metrics = facpService.getSystemMetrics();
      
      res.json({
        status: 'operational',
        timestamp: new Date().toISOString(),
        version: 'FACP/1.1',
        uptime: metrics.uptime_seconds,
        active_requests: metrics.active_requests,
        total_executions: metrics.total_executions
      });
    } catch (error) {
      console.error('Error in health check:', error);
      res.status(500).json({
        status: 'degraded',
        error: error.message
      });
    }
  });

  /**
   * Get protocol specification
   */
  app.get('/api/facp/spec', (req, res) => {
    res.json({
      protocol: 'FACP/1.1',
      version: '1.1.0',
      specification: {
        request: {
          required_fields: ['protocol', 'id', 'timestamp', 'source', 'target', 'method', 'params', 'security'],
          optional_fields: ['constraints', 'execution_state'],
          security_block: ['auth_token', 'permissions', 'risk_level', 'idempotency_key'],
          constraints: ['timeout_ms', 'max_memory_mb', 'max_recursion_depth']
        },
        response: {
          required_fields: ['protocol', 'id', 'status'],
          optional_fields: ['result', 'error', 'trace']
        }
      },
      timestamp: new Date().toISOString()
    });
  });
};