/**
 * CoverageEngine.ts - NFPA 72 Coverage Calculation Engine
 * Calculates detector coverage per NFPA 72 requirements
 */

interface Room {
  id: string;
  name: string;
  width: number; // in meters
  length: number; // in meters
  height: number; // in meters
  ceilingType: 'flat' | 'sloped' | 'coffered';
  occupancy: string;
}

interface Detector {
  id: string;
  roomId: string;
  type: 'smoke' | 'heat' | 'rate-of-rise' | 'flame-detector';
  x: number; // position in room
  y: number; // position in room
  coverageRadius: number; // in meters
  sensitivity: 'high' | 'standard' | 'low';
}

interface CoverageResult {
  roomId: string;
  roomName: string;
  detectorCount: number;
  coveragePercentage: number;
  pass: boolean;
  uncoveredAreas: { x: number; y: number; area: number }[];
  nfpaReference: string;
}

interface CoverageCalculation {
  summary: {
    totalRooms: number;
    totalDetectors: number;
    coveragePercentage: number;
    passedRooms: number;
    failedRooms: number;
  };
  roomResults: CoverageResult[];
}

/**
 * Calculates coverage for a single room
 * 
 * @param room The room to calculate coverage for
 * @param detectors Detectors in the room
 * @returns Coverage result for the room
 */
export function calculateRoomCoverage(room: Room, detectors: Detector[]): CoverageResult {
  // Create a grid to represent the room
  const gridSize = 0.5; // 0.5m grid resolution
  const cols = Math.ceil(room.width / gridSize);
  const rows = Math.ceil(room.length / gridSize);
  
  // Initialize grid - false means uncovered
  const grid: boolean[][] = Array(rows).fill(null).map(() => Array(cols).fill(false));
  
  // Mark covered areas based on detector positions and coverage radii
  detectors.forEach(detector => {
    const centerX = detector.x / gridSize;
    const centerY = detector.y / gridSize;
    const radiusInGrid = detector.coverageRadius / gridSize;
    const radiusSquared = radiusInGrid * radiusInGrid;
    
    // Check each cell in the grid
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const dx = col - centerX;
        const dy = row - centerY;
        const distanceSquared = dx * dx + dy * dy;
        
        if (distanceSquared <= radiusSquared) {
          // Mark as covered
          grid[row][col] = true;
        }
      }
    }
  });
  
  // Count covered vs uncovered cells
  let coveredCells = 0;
  const uncoveredAreas: { x: number; y: number; area: number }[] = [];
  
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      if (grid[row][col]) {
        coveredCells++;
      } else {
        // Record uncovered area for reporting
        uncoveredAreas.push({
          x: col * gridSize,
          y: row * gridSize,
          area: gridSize * gridSize
        });
      }
    }
  }
  
  const totalCells = rows * cols;
  const coveragePercentage = totalCells > 0 ? (coveredCells / totalCells) * 100 : 0;
  
  // Determine if coverage passes based on occupancy type and detector type
  let pass = false;
  let nfpaReference = '';
  
  if (room.occupancy.toLowerCase().includes('high')) {
    // High hazard occupancy - typically requires 90%+ coverage
    pass = coveragePercentage >= 90;
    nfpaReference = 'NFPA 72 17.7.5.2.2';
  } else if (room.occupancy.toLowerCase().includes('medium')) {
    // Medium hazard occupancy - typically requires 80%+ coverage
    pass = coveragePercentage >= 80;
    nfpaReference = 'NFPA 72 17.7.5.2.2';
  } else {
    // Standard occupancy - requires 70%+ coverage
    pass = coveragePercentage >= 70;
    nfpaReference = 'NFPA 72 17.7.5.2.2';
  }
  
  // Special cases based on detector type
  if (detectors.some(d => d.type === 'heat')) {
    // Heat detectors may have different spacing requirements
    nfpaReference = 'NFPA 72 17.7.5.3';
  }
  
  return {
    roomId: room.id,
    roomName: room.name,
    detectorCount: detectors.length,
    coveragePercentage,
    pass,
    uncoveredAreas,
    nfpaReference
  };
}

/**
 * Calculates coverage for multiple rooms
 * 
 * @param rooms List of rooms to calculate coverage for
 * @param detectors List of all detectors
 * @returns Overall coverage calculation result
 */
export function calculateCoverage(rooms: Room[], detectors: Detector[]): CoverageCalculation {
  const roomResults: CoverageResult[] = [];
  
  rooms.forEach(room => {
    const roomDetectors = detectors.filter(d => d.roomId === room.id);
    const result = calculateRoomCoverage(room, roomDetectors);
    roomResults.push(result);
  });
  
  // Calculate summary
  const totalRooms = rooms.length;
  const totalDetectors = detectors.length;
  const passedRooms = roomResults.filter(r => r.pass).length;
  const failedRooms = roomResults.filter(r => !r.pass).length;
  const overallCoverage = roomResults.reduce((sum, r) => sum + r.coveragePercentage, 0) / totalRooms;
  
  return {
    summary: {
      totalRooms,
      totalDetectors,
      coveragePercentage: parseFloat(overallCoverage.toFixed(2)),
      passedRooms,
      failedRooms
    },
    roomResults
  };
}

/**
 * Generates a detailed coverage report
 * 
 * @param calculation Coverage calculation result
 * @returns Formatted coverage report
 */
export function generateCoverageReport(calculation: CoverageCalculation): string {
  let report = '';
  report += 'NFPA 72 COVERAGE ANALYSIS REPORT\n';
  report += '=================================\n\n';
  
  report += 'SUMMARY:\n';
  report += '--------\n';
  report += `Total Rooms: ${calculation.summary.totalRooms}\n`;
  report += `Total Detectors: ${calculation.summary.totalDetectors}\n`;
  report += `Overall Coverage: ${calculation.summary.coveragePercentage}%\n`;
  report += `Passed Rooms: ${calculation.summary.passedRooms}\n`;
  report += `Failed Rooms: ${calculation.summary.failedRooms}\n\n`;
  
  report += 'ROOM-BY-ROOM BREAKDOWN:\n';
  report += '----------------------\n';
  
  calculation.roomResults.forEach(result => {
    report += `Room: ${result.roomName}\n`;
    report += `  Detectors: ${result.detectorCount}\n`;
    report += `  Coverage: ${result.coveragePercentage.toFixed(2)}%\n`;
    report += `  Status: ${result.pass ? 'PASS' : 'FAIL'}\n`;
    report += `  NFPA Reference: ${result.nfpaReference}\n`;
    report += `  Uncovered Areas: ${result.uncoveredAreas.length}\n\n`;
  });
  
  report += 'COMPLIANCE NOTES:\n';
  report += '-----------------\n';
  report += 'Per NFPA 72 2020 Edition:\n';
  report += '- Coverage requirements vary by occupancy and detector type\n';
  report += '- Standard occupancy requires minimum 70% coverage\n';
  report += '- High hazard occupancy requires minimum 90% coverage\n';
  report += '- Maximum detector spacing per Table 17.7.5.2.2\n';
  report += '- Sloped ceilings may require closer spacing\n';
  
  return report;
}

/**
 * Validates detector placement per NFPA 72 requirements
 * 
 * @param room Room configuration
 * @param detectors Detectors in the room
 * @returns Validation result with compliance status
 */
export function validateDetectorPlacement(room: Room, detectors: Detector[]): {
  compliant: boolean;
  warnings: string[];
  errors: string[];
} {
  const warnings: string[] = [];
  const errors: string[] = [];
  
  detectors.forEach(detector => {
    // Check if detector is placed within the room boundaries
    if (detector.x > room.width || detector.y > room.length) {
      errors.push(`Detector ${detector.id} is outside room boundaries`);
    }
    
    // Check if detector is too close to walls (typically 0.5m minimum)
    if (detector.x < 0.5 || detector.y < 0.5 || 
        detector.x > room.width - 0.5 || detector.y > room.length - 0.5) {
      warnings.push(`Detector ${detector.id} is close to wall (less than 0.5m)`);
    }
    
    // Check detector spacing based on type and ceiling height
    if (detector.type === 'smoke' && room.height > 3 && detector.coverageRadius > 6.37) {
      errors.push(`Smoke detector ${detector.id} exceeds maximum coverage radius for ceiling height >3m`);
    }
    
    if (detector.type === 'heat' && room.height > 3 && detector.coverageRadius > 4.27) {
      errors.push(`Heat detector ${detector.id} exceeds maximum coverage radius for ceiling height >3m`);
    }
  });
  
  // Check for adequate detector density
  const area = room.width * room.length;
  const requiredDetectors = Math.ceil(area / 100); // Simplified: 1 detector per 100 sqm as minimum
  if (detectors.length < requiredDetectors) {
    warnings.push(`Room ${room.name} may require more detectors for optimal coverage`);
  }
  
  return {
    compliant: errors.length === 0,
    warnings,
    errors
  };
}