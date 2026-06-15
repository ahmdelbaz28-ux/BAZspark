import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, ChevronDown, Folder, FolderOpen, MonitorSpeaker, Flame, Thermometer, Volume2, VolumeX, Square, Settings, Cpu } from 'lucide-react';

interface Device {
  id: string;
  name: string;
  type: string;
  zone: string;
  status: 'normal' | 'warning' | 'fault';
  address: string;
}

interface Zone {
  id: string;
  name: string;
  parent?: string;
  type: 'panel' | 'loop' | 'circuit' | 'zone' | 'integration';
  devices: Device[];
  children?: Zone[];
}

interface ZoneNodeProps {
  zone: Zone;
  level: number;
  selectedDevice: string | null;
  onDeviceSelect: (deviceId: string) => void;
  onZoomToZone: (zoneId: string) => void;
}

const ZoneNode: React.FC<ZoneNodeProps> = ({ 
  zone, 
  level, 
  selectedDevice, 
  onDeviceSelect, 
  onZoomToZone 
}) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(level < 2); // Expand first 2 levels by default

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Get appropriate icon based on zone type
  const getZoneIcon = () => {
    switch (zone.type) {
      case 'panel':
        return <Cpu className="w-4 h-4 text-blue-400" />;
      case 'loop':
        return <Settings className="w-4 h-4 text-purple-400" />;
      case 'circuit':
        return <Square className="w-4 h-4 text-yellow-400" />;
      case 'integration':
        return <MonitorSpeaker className="w-4 h-4 text-green-400" />;
      case 'zone':
      default:
        return <Folder className="w-4 h-4 text-amber-400" />;
    }
  };

  // Get device icon based on type
  const getDeviceIcon = (type: string) => {
    switch (type) {
      case 'smoke':
        return <Flame className="w-3 h-3 text-red-400" />;
      case 'heat':
        return <Thermometer className="w-3 h-3 text-orange-400" />;
      case 'horns':
        return <Volume2 className="w-3 h-3 text-blue-400" />;
      case 'horns-fault':
        return <VolumeX className="w-3 h-3 text-red-400" />;
      default:
        return <Flame className="w-3 h-3 text-gray-400" />;
    }
  };

  // Get status color
  const getStatusColor = (status: 'normal' | 'warning' | 'fault') => {
    switch (status) {
      case 'normal':
        return 'text-green-400';
      case 'warning':
        return 'text-amber-400';
      case 'fault':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <div>
      <div 
        className={`flex items-center py-1 px-2 rounded cursor-pointer hover:bg-slate-700 ${
          zone.children && zone.children.length > 0 ? 'group' : ''
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={zone.children && zone.children.length > 0 ? toggleExpanded : () => onZoomToZone(zone.id)}
      >
        {zone.children && zone.children.length > 0 ? (
          <div className="mr-1">
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-slate-400 group-hover:text-slate-200" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-200" />
            )}
          </div>
        ) : (
          <div className="w-5 h-4 mr-1" /> // Spacer for alignment
        )}
        
        {getZoneIcon()}
        <span className="ml-2 text-slate-200 text-sm truncate">
          {zone.name}
        </span>
        {zone.devices && zone.devices.length > 0 && (
          <span className="ml-2 text-xs text-slate-400">
            ({zone.devices.length})
          </span>
        )}
      </div>
      
      {isExpanded && zone.children && zone.children.map(child => (
        <ZoneNode
          key={child.id}
          zone={child}
          level={level + 1}
          selectedDevice={selectedDevice}
          onDeviceSelect={onDeviceSelect}
          onZoomToZone={onZoomToZone}
        />
      ))}
      
      {isExpanded && zone.devices && zone.devices.map(device => (
        <div
          key={device.id}
          className={`flex items-center py-1 px-2 rounded cursor-pointer hover:bg-slate-700 ${
            selectedDevice === device.id ? 'bg-slate-700' : ''
          }`}
          style={{ paddingLeft: `${(level + 1) * 16 + 8}px` }}
          onClick={() => onDeviceSelect(device.id)}
        >
          <div className="w-5 h-4 mr-1" /> {/* Indent for devices */}
          {getDeviceIcon(device.type)}
          <span className="ml-2 text-slate-300 text-sm truncate">
            {device.name}
          </span>
          <div className={`w-2 h-2 rounded-full ml-2 ${getStatusColor(device.status)}`}></div>
        </div>
      ))}
    </div>
  );
};

interface ZoneNavigatorProps {
  zones: Zone[];
  selectedDevice: string | null;
  onDeviceSelect: (deviceId: string) => void;
  onZoomToZone: (zoneId: string) => void;
}

export const ZoneNavigator: React.FC<ZoneNavigatorProps> = ({ 
  zones, 
  selectedDevice, 
  onDeviceSelect,
  onZoomToZone
}) => {
  const { t } = useTranslation();
  
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 w-64 h-full overflow-y-auto">
      <h3 className="text-lg font-semibold text-slate-100 mb-3 flex items-center">
        <FolderOpen className="w-5 h-5 mr-2" />
        {t('fireAlarm.systemNavigator')}
      </h3>
      
      <div className="space-y-1">
        {zones.map(zone => (
          <ZoneNode
            key={zone.id}
            zone={zone}
            level={0}
            selectedDevice={selectedDevice}
            onDeviceSelect={onDeviceSelect}
            onZoomToZone={onZoomToZone}
          />
        ))}
      </div>
    </div>
  );
};