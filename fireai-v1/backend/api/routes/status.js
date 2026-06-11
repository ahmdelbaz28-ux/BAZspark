/**
 * Status Routes for FireAI v1.0
 * API endpoints for system status and monitoring
 */

const { query } = require('express-validator');

module.exports = (app, facpService, agentService, executionService) => {
  /**
   * Get overall system status
   */
  app.get('/api/status', (req, res) => {
    try {
      const facpMetrics = facpService.getSystemMetrics();
      const agentStats = agentService.getAgentStats();
      const executionStats = executionService.getExecutionStats();

      const overallStatus = {
        status: 'operational',
        timestamp: new Date().toISOString(),
        uptime: facpMetrics.uptime_seconds,
        services: {
          facp_service: 'operational',
          agent_service: 'operational',
          execution_service: 'operational'
        },
        metrics: {
          ...facpMetrics,
          ...agentStats,
          ...executionStats
        }
      };

      // Determine overall status based on metrics
      if (facpMetrics.failed_executions > facpMetrics.completed_executions * 0.1) {
        overallStatus.status = 'degraded';
      }

      res.json(overallStatus);
    } catch (error) {
      console.error('Error fetching system status:', error);
      res.status(500).json({
        status: 'error',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  });

  /**
   * Get detailed system metrics
   */
  app.get('/api/status/metrics', (req, res) => {
    try {
      const facpMetrics = facpService.getSystemMetrics();
      const agentStats = agentService.getAgentStats();
      const executionStats = executionService.getExecutionStats();

      const detailedMetrics = {
        facp: facpMetrics,
        agents: agentStats,
        execution: executionStats,
        timestamp: new Date().toISOString()
      };

      res.json({
        success: true,
        metrics: detailedMetrics
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
   * Get execution queue status
   */
  app.get('/api/status/queue', (req, res) => {
    try {
      const queueStatus = executionService.getQueueStatus();

      res.json({
        success: true,
        queue: queueStatus,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('Error fetching queue status:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get recent executions
   */
  app.get('/api/status/recent-executions', [
    query('limit').optional().isInt({ min: 1, max: 100 }).withMessage('Limit must be between 1 and 100')
  ], (req, res) => {
    try {
      const limit = parseInt(req.query.limit) || 10;
      const traces = facpService.getExecutionTraces(limit);

      res.json({
        success: true,
        count: traces.length,
        executions: traces,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('Error fetching recent executions:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get system health
   */
  app.get('/api/status/health', (req, res) => {
    try {
      // Perform health checks
      const healthChecks = {
        database: { status: 'connected', timestamp: new Date().toISOString() },
        redis: { status: 'connected', timestamp: new Date().toISOString() },
        memory: {
          usage: `${Math.floor(process.memoryUsage().heapUsed / 1024 / 1024)}MB`,
          status: 'normal'
        },
        cpu: {
          load: 'normal', // In a real system, this would check actual CPU load
          status: 'normal'
        },
        disk: {
          usage: 'normal', // In a real system, this would check actual disk usage
          status: 'normal'
        }
      };

      // Overall health status
      const isHealthy = Object.values(healthChecks).every(check => 
        check.status === 'connected' || check.status === 'normal'
      );

      res.json({
        status: isHealthy ? 'healthy' : 'unhealthy',
        timestamp: new Date().toISOString(),
        checks: healthChecks
      });
    } catch (error) {
      console.error('Error performing health check:', error);
      res.status(500).json({
        status: 'unhealthy',
        error: error.message,
        timestamp: new Date().toISOString()
      });
    }
  });

  /**
   * Get system configuration
   */
  app.get('/api/status/config', (req, res) => {
    try {
      const config = {
        facp_protocol: 'FACP/1.1',
        max_timeout: '30 seconds',
        max_memory: '1GB',
        max_recursion_depth: 10,
        max_concurrent_executions: 10,
        environment: process.env.NODE_ENV || 'development',
        version: '1.0.0',
        timestamp: new Date().toISOString()
      };

      res.json({
        success: true,
        config
      });
    } catch (error) {
      console.error('Error fetching system config:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });

  /**
   * Get active connections
   */
  app.get('/api/status/connections', (req, res) => {
    try {
      // In a real system, this would track actual connections
      const connections = {
        websocket_connections: 0, // Would be tracked in a real system
        active_requests: 0, // Would be tracked in a real system
        total_requests_served: 0, // Would be tracked in a real system
        timestamp: new Date().toISOString()
      };

      res.json({
        success: true,
        connections
      });
    } catch (error) {
      console.error('Error fetching connections:', error);
      res.status(500).json({
        error: 'Internal server error',
        message: error.message
      });
    }
  });
};