import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Badge } from '../ui/badge';
import { Activity, AlertTriangle, CheckCircle2, ShieldOff } from 'lucide-react';

interface Zone {
  id: string;
  name: string;
  status: 'NORMAL' | 'ALARM' | 'FAULT' | 'ISOLATED';
  deviceCount: number;
  lastTested?: string;
}

const MOCK_ZONES: Zone[] = [
  { id: 'Z01', name: 'Ground Floor Lobby', status: 'NORMAL', deviceCount: 12, lastTested: '2026-08-01' },
  { id: 'Z02', name: 'Server Room', status: 'NORMAL', deviceCount: 4, lastTested: '2026-08-01' },
  { id: 'Z03', name: 'Cafeteria', status: 'ALARM', deviceCount: 8, lastTested: '2026-08-02' },
  { id: 'Z04', name: 'Warehouse A', status: 'ISOLATED', deviceCount: 24, lastTested: '2026-07-15' },
];

export const ZoneStatusPanel: React.FC = () => {
  const [zones] = useState<Zone[]>(MOCK_ZONES);

  const getStatusIcon = (status: Zone['status']) => {
    switch (status) {
      case 'NORMAL': return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case 'ALARM': return <Activity className="h-4 w-4 text-destructive animate-pulse" />;
      case 'FAULT': return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      case 'ISOLATED': return <ShieldOff className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: Zone['status']) => {
    switch (status) {
      case 'NORMAL': return <Badge variant="outline" className="border-emerald-500 text-emerald-500">Normal</Badge>;
      case 'ALARM': return <Badge variant="destructive" className="animate-pulse">Fire Alarm</Badge>;
      case 'FAULT': return <Badge variant="secondary" className="bg-amber-500/10 text-amber-600">Fault</Badge>;
      case 'ISOLATED': return <Badge variant="secondary">Isolated</Badge>;
    }
  };

  return (
    <Card className="col-span-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Network Zone Status
        </CardTitle>
        <CardDescription>Real-time monitoring per NFPA 72 requirements</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {zones.map((zone) => (
            <div key={zone.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors">
              <div className="flex items-center gap-3">
                {getStatusIcon(zone.status)}
                <div>
                  <p className="text-sm font-medium leading-none">{zone.id} - {zone.name}</p>
                  <p className="text-xs text-muted-foreground mt-1">{zone.deviceCount} Devices Active</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-muted-foreground">Tested: {zone.lastTested}</span>
                {getStatusBadge(zone.status)}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
