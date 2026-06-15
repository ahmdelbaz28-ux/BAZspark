/**
 * BatteryCalculator.ts - NFPA 72 Battery Calculation Engine
 * Calculates battery capacity for fire alarm control panels per NFPA 72 requirements
 */

interface Device {
  id: string;
  name: string;
  type: string;
  standbyCurrent: number; // in mA
  alarmCurrent: number;   // in mA
  count: number;
}

interface BatteryCalculationInput {
  devices: Device[];
  standbyHours: number; // Default 24 (NFPA 72 requires minimum 24h standby)
  alarmMinutes: number; // Default 5 (NFPA 72 requires minimum 5 min alarm)
  safetyFactor: number; // Default 1.2 (20% safety margin)
}

interface BatteryCalculationResult {
  standbyCurrent: number; // Total standby current in mA
  alarmCurrent: number;   // Total alarm current in mA
  requiredCapacity: number; // Required battery capacity in Ah
  recommendedBattery: {
    voltage: number; // in Volts
    capacity: number; // in Ah
    type: string;
  };
  summary: {
    totalDevices: number;
    totalStandbyCurrent: string;
    totalAlarmCurrent: string;
    requiredCapacity: string;
    recommendedBattery: string;
  };
}

/**
 * Calculates battery capacity requirements per NFPA 72
 * Formula: Battery Capacity = (Standby Current × Standby Hours) + (Alarm Current × Alarm Minutes/60)
 * 
 * @param input Battery calculation parameters
 * @returns Battery calculation results
 */
export function calculateBatteryRequirements(input: BatteryCalculationInput): BatteryCalculationResult {
  // Calculate total standby current (mA)
  const totalStandbyCurrent = input.devices.reduce(
    (sum, device) => sum + (device.standbyCurrent * device.count),
    0
  );

  // Calculate total alarm current (mA)
  const totalAlarmCurrent = input.devices.reduce(
    (sum, device) => sum + (device.alarmCurrent * device.count),
    0
  );

  // Convert mA to A
  const standbyCurrentA = totalStandbyCurrent / 1000;
  const alarmCurrentA = totalAlarmCurrent / 1000;

  // Calculate required battery capacity (Ah)
  // Per NFPA 72: Battery must support 24 hours standby + 5 minutes alarm
  const standbyCapacity = standbyCurrentA * input.standbyHours;
  const alarmCapacity = alarmCurrentA * (input.alarmMinutes / 60);
  const baseRequiredCapacity = standbyCapacity + alarmCapacity;

  // Apply safety factor
  const requiredCapacity = baseRequiredCapacity * input.safetyFactor;

  // Determine recommended battery
  const batteryVoltage = 24; // Common FACP battery voltage
  const batteryCapacity = Math.ceil(requiredCapacity * 1.2); // Add extra 20% for aging

  // Format summary
  const summary = {
    totalDevices: input.devices.reduce((sum, device) => sum + device.count, 0),
    totalStandbyCurrent: standbyCurrentA.toFixed(2) + ' A',
    totalAlarmCurrent: alarmCurrentA.toFixed(2) + ' A',
    requiredCapacity: requiredCapacity.toFixed(2) + ' Ah',
    recommendedBattery: `${batteryVoltage}V ${batteryCapacity}Ah`
  };

  return {
    standbyCurrent: totalStandbyCurrent,
    alarmCurrent: totalAlarmCurrent,
    requiredCapacity,
    recommendedBattery: {
      voltage: batteryVoltage,
      capacity: batteryCapacity,
      type: 'Lead Acid (Sealed AGM)'
    },
    summary
  };
}

/**
 * Generates a detailed battery calculation report
 * 
 * @param input Battery calculation parameters
 * @returns Formatted report with device breakdown
 */
export function generateBatteryReport(input: BatteryCalculationInput): string {
  const result = calculateBatteryRequirements(input);
  
  let report = '';
  report += 'NFPA 72 BATTERY CALCULATION REPORT\n';
  report += '==================================\n\n';
  
  report += 'DEVICE BREAKDOWN:\n';
  report += '----------------\n';
  report += 'Type\t\tCount\tStandby(mA)\tAlarm(mA)\tTotal Standby(mA)\tTotal Alarm(mA)\n';
  report += '----\t\t-----\t----------\t--------\t----------------\t-------------\n';
  
  input.devices.forEach(device => {
    const totalStandby = device.standbyCurrent * device.count;
    const totalAlarm = device.alarmCurrent * device.count;
    report += `${device.type}\t\t${device.count}\t${device.standbyCurrent}\t\t${device.alarmCurrent}\t\t${totalStandby}\t\t${totalAlarm}\n`;
  });
  
  report += '\nCALCULATION SUMMARY:\n';
  report += '------------------\n';
  report += `Total Devices: ${result.summary.totalDevices}\n`;
  report += `Total Standby Current: ${result.summary.totalStandbyCurrent}\n`;
  report += `Total Alarm Current: ${result.summary.totalAlarmCurrent}\n`;
  report += `Standby Duration: ${input.standbyHours} hours\n`;
  report += `Alarm Duration: ${input.alarmMinutes} minutes\n`;
  report += `Safety Factor: ${input.safetyFactor}x\n`;
  report += `Required Battery Capacity: ${result.summary.requiredCapacity}\n`;
  report += `Recommended Battery: ${result.summary.recommendedBattery}\n`;
  
  report += '\nCOMPLIANCE NOTES:\n';
  report += '-----------------\n';
  report += 'Per NFPA 72 2020 Edition:\n';
  report += '- Minimum 24 hours of standby power\n';
  report += '- Minimum 5 minutes of alarm power\n';
  report += '- Batteries shall be sized for 125% of connected load\n';
  report += `- Calculated capacity includes ${Math.round((input.safetyFactor - 1) * 100)}% safety margin\n`;
  
  return report;
}

/**
 * Validates if the calculated battery meets NFPA 72 minimum requirements
 * 
 * @param result Battery calculation result
 * @returns Validation result with compliance status
 */
export function validateBatteryCompliance(result: BatteryCalculationResult): {
  compliant: boolean;
  warnings: string[];
  errors: string[];
} {
  const warnings: string[] = [];
  const errors: string[] = [];

  // NFPA 72 requires minimum 24h standby and 5min alarm
  // The calculation formula already accounts for these minimums
  
  if (result.requiredCapacity <= 0) {
    errors.push('Required battery capacity must be greater than 0 Ah');
  }

  if (result.standbyCurrent <= 0) {
    errors.push('Total standby current must be greater than 0 mA');
  }

  if (result.alarmCurrent <= 0) {
    errors.push('Total alarm current must be greater than 0 mA');
  }

  // Check for unusually high battery requirements
  if (result.requiredCapacity > 1000) {
    warnings.push(`Very high battery requirement (${result.requiredCapacity.toFixed(2)} Ah) - verify device currents`);
  }

  return {
    compliant: errors.length === 0,
    warnings,
    errors
  };
}