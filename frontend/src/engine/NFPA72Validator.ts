/**
 * NFPA72Validator.ts - NFPA 72 Compliance Validation Engine
 * Validates fire alarm system designs against NFPA 72 requirements
 */

interface Device {
  id: string;
  name: string;
  type: 'smoke' | 'heat' | 'pull-station' | 'notification-appliance' | 'control-equipment';
  location: string;
  zone: string;
  loop: string;
  address: string;
  manufacturer: string;
  model: string;
  sensitivity?: number;
  coverageRadius?: number;
  standbyCurrent?: number;
  alarmCurrent?: number;
}

interface SystemConfiguration {
  devices: Device[];
  panels: {
    id: string;
    type: 'FACP' | 'ANC' | 'DRP';
    manufacturer: string;
    model: string;
    loopCount: number;
    notificationAppliances: number;
    detectionDevices: number;
    standbyCurrent: number;
    alarmCurrent: number;
  }[];
  loops: {
    id: string;
    type: 'SLC' | 'NAC';
    devices: string[];
    length: number;
    wireGauge: string;
    voltageDrop: number;
  }[];
  zones: {
    id: string;
    type: 'initiating' | 'notification';
    devices: string[];
    priority: 'normal' | 'high' | 'life-safety';
  }[];
}

interface ValidationResult {
  compliant: boolean;
  issues: {
    severity: 'critical' | 'warning' | 'info';
    code: string; // NFPA 72 section number
    description: string;
    deviceIds?: string[];
    recommendations: string[];
  }[];
}

/**
 * Validates an entire fire alarm system configuration against NFPA 72
 * 
 * @param config System configuration to validate
 * @returns Validation result with compliance status and issues
 */
export function validateNFPA72Compliance(config: SystemConfiguration): ValidationResult {
  const issues: ValidationResult['issues'] = [];
  
  // Validate panel configurations
  config.panels.forEach(panel => {
    // Check panel capacity
    if (panel.detectionDevices > 159) {
      issues.push({
        severity: 'critical',
        code: 'NFPA 72 10.15.2.2',
        description: `Panel ${panel.id} exceeds maximum of 159 detection devices`,
        recommendations: ['Reduce number of devices on this panel', 'Add additional panels']
      });
    }
    
    if (panel.notificationAppliances > 159) {
      issues.push({
        severity: 'critical',
        code: 'NFPA 72 10.15.2.3',
        description: `Panel ${panel.id} exceeds maximum of 159 notification appliances`,
        recommendations: ['Reduce number of notification appliances on this panel', 'Add additional panels']
      });
    }
    
    // Check voltage drop on notification appliance circuits
    config.loops.filter(l => l.type === 'NAC').forEach(loop => {
      if (loop.voltageDrop > 1.5) {
        issues.push({
          severity: 'critical',
          code: 'NFPA 72 21.4.4',
          description: `NAC loop ${loop.id} voltage drop (${loop.voltageDrop}V) exceeds 1.5V limit`,
          recommendations: [
            'Use larger wire gauge',
            'Reduce loop length',
            'Add boosters'
          ]
        });
      }
    });
  });
  
  // Validate detector placement
  const smokeDetectors = config.devices.filter(d => d.type === 'smoke');
  const heatDetectors = config.devices.filter(d => d.type === 'heat');
  
  smokeDetectors.forEach(detector => {
    // Check for smoke detector spacing compliance
    if (detector.coverageRadius && detector.coverageRadius > 6.37) {
      issues.push({
        severity: 'critical',
        code: 'NFPA 72 17.7.5.2.2',
        description: `Smoke detector ${detector.id} exceeds maximum 6.37m coverage radius`,
        deviceIds: [detector.id],
        recommendations: [
          'Reduce coverage radius to 6.37m or less',
          'Add additional detectors'
        ]
      });
    }
  });
  
  heatDetectors.forEach(detector => {
    // Check for heat detector spacing compliance
    if (detector.coverageRadius && detector.coverageRadius > 4.27) {
      issues.push({
        severity: 'critical',
        code: 'NFPA 72 17.7.5.3',
        description: `Heat detector ${detector.id} exceeds maximum 4.27m coverage radius`,
        deviceIds: [detector.id],
        recommendations: [
          'Reduce coverage radius to 4.27m or less',
          'Add additional detectors'
        ]
      });
    }
  });
  
  // Validate pull stations
  const pullStations = config.devices.filter(d => d.type === 'pull-station');
  const mainEntrances = pullStations.filter(ps => ps.location.includes('entrance'));
  
  if (mainEntrances.length === 0) {
    issues.push({
      severity: 'warning',
      code: 'NFPA 72 21.3.2',
      description: 'No manual fire alarm boxes at main entrances detected',
      recommendations: [
        'Install manual fire alarm boxes at main entrances',
        'Ensure boxes are accessible and clearly marked'
      ]
    });
  }
  
  // Validate zone classifications
  config.zones.forEach(zone => {
    if (zone.priority === 'life-safety' && zone.type !== 'notification') {
      issues.push({
        severity: 'warning',
        code: 'NFPA 72 10.15.7',
        description: `Life safety zone ${zone.id} is not a notification zone`,
        recommendations: [
          'Ensure life safety zones include notification appliances',
          'Separate initiating and notification zones as required'
        ]
      });
    }
  });
  
  // Check for required system monitoring
  const notificationLoops = config.loops.filter(l => l.type === 'NAC');
  if (notificationLoops.length === 0) {
    issues.push({
      severity: 'critical',
      code: 'NFPA 72 10.15.1',
      description: 'No notification appliance circuits detected',
      recommendations: [
        'Install notification appliance circuits',
        'Connect audible/visual notification devices'
      ]
    });
  }
  
  // Check for proper battery backup
  const facpPanels = config.panels.filter(p => p.type === 'FACP');
  facpPanels.forEach(panel => {
    // In a real validation, we would check battery calculations
    if (panel.standbyCurrent > 10000 || panel.alarmCurrent > 10000) { // Example thresholds
      issues.push({
        severity: 'warning',
        code: 'NFPA 72 10.15.4',
        description: `Panel ${panel.id} has high current draw - verify battery capacity`,
        recommendations: [
          'Calculate required battery capacity',
          'Verify batteries meet 24hr standby + 5min alarm requirement'
        ]
      });
    }
  });
  
  return {
    compliant: issues.filter(i => i.severity === 'critical').length === 0,
    issues
  };
}

/**
 * Validates individual device compliance
 * 
 * @param device Device to validate
 * @returns Validation result for the device
 */
export function validateDevice(device: Device): {
  compliant: boolean;
  issues: {
    severity: 'critical' | 'warning' | 'info';
    code: string;
    description: string;
    recommendations: string[];
  }[];
} {
  const issues: {
    severity: 'critical' | 'warning' | 'info';
    code: string;
    description: string;
    recommendations: string[];
  }[] = [];
  
  // Check device addressing
  if (!device.address || device.address.trim() === '') {
    issues.push({
      severity: 'critical',
      code: 'NFPA 72 10.15.6',
      description: 'Device has no address assigned',
      recommendations: ['Assign unique address to device']
    });
  }
  
  // Check zone assignment
  if (!device.zone || device.zone.trim() === '') {
    issues.push({
      severity: 'critical',
      code: 'NFPA 72 10.15.7',
      description: 'Device not assigned to a zone',
      recommendations: ['Assign device to appropriate zone']
    });
  }
  
  // Validate device type-specific requirements
  switch (device.type) {
    case 'smoke':
      if (!device.coverageRadius || device.coverageRadius > 6.37) {
        issues.push({
          severity: 'critical',
          code: 'NFPA 72 17.7.5.2.2',
          description: 'Smoke detector exceeds maximum coverage radius',
          recommendations: ['Verify coverage radius is ≤6.37m']
        });
      }
      break;
      
    case 'heat':
      if (!device.coverageRadius || device.coverageRadius > 4.27) {
        issues.push({
          severity: 'critical',
          code: 'NFPA 72 17.7.5.3',
          description: 'Heat detector exceeds maximum coverage radius',
          recommendations: ['Verify coverage radius is ≤4.27m']
        });
      }
      break;
      
    case 'pull-station':
      if (!device.location.includes('accessible') && !device.location.includes('exit') && !device.location.includes('entrance')) {
        issues.push({
          severity: 'warning',
          code: 'NFPA 72 21.3.2',
          description: 'Pull station location may not be optimally accessible',
          recommendations: ['Position pull stations at main entrances/exits', 'Ensure accessibility']
        });
      }
      break;
  }
  
  return {
    compliant: issues.filter(i => i.severity === 'critical').length === 0,
    issues
  };
}

/**
 * Generates a compliance report from validation results
 * 
 * @param result Validation result to format
 * @returns Formatted compliance report
 */
export function generateComplianceReport(result: ValidationResult): string {
  let report = '';
  report += 'NFPA 72 COMPLIANCE VALIDATION REPORT\n';
  report += '=====================================\n\n';
  
  report += `Overall Compliance Status: ${result.compliant ? 'PASS' : 'FAIL'}\n\n`;
  
  if (result.issues.length === 0) {
    report += 'No compliance issues detected.\n';
    return report;
  }
  
  // Group issues by severity
  const criticalIssues = result.issues.filter(i => i.severity === 'critical');
  const warningIssues = result.issues.filter(i => i.severity === 'warning');
  const infoIssues = result.issues.filter(i => i.severity === 'info');
  
  if (criticalIssues.length > 0) {
    report += 'CRITICAL ISSUES (Must be resolved):\n';
    report += '-----------------------------------\n';
    criticalIssues.forEach(issue => {
      report += `- ${issue.code}: ${issue.description}\n`;
      report += `  Recommendations: ${issue.recommendations.join('; ')}\n\n`;
    });
  }
  
  if (warningIssues.length > 0) {
    report += 'WARNING ISSUES (Should be addressed):\n';
    report += '-------------------------------------\n';
    warningIssues.forEach(issue => {
      report += `- ${issue.code}: ${issue.description}\n`;
      report += `  Recommendations: ${issue.recommendations.join('; ')}\n\n`;
    });
  }
  
  if (infoIssues.length > 0) {
    report += 'INFORMATIONAL ITEMS:\n';
    report += '--------------------\n';
    infoIssues.forEach(issue => {
      report += `- ${issue.code}: ${issue.description}\n`;
      report += `  Notes: ${issue.recommendations.join('; ')}\n\n`;
    });
  }
  
  report += 'COMPLIANCE SUMMARY:\n';
  report += '-------------------\n';
  report += `Critical Issues: ${criticalIssues.length}\n`;
  report += `Warnings: ${warningIssues.length}\n`;
  report += `Informational Items: ${infoIssues.length}\n`;
  report += `Total Issues: ${result.issues.length}\n`;
  
  return report;
}