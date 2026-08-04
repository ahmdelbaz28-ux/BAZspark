import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertCircle, Save, CheckCircle2 } from 'lucide-react';

type FeatureFlags = Record<string, boolean>;

export function FeatureFlagManager() {
  const [flags, setFlags] = useState<FeatureFlags>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetch('http://localhost:7860/settings/feature-flags', {
      headers: {
        'X-API-Key': 'dev-key-123' // Or get from auth context
      }
    })
      .then(res => res.json())
      .then(data => {
        setFlags(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load feature flags', err);
        setLoading(false);
      });
  }, []);

  const handleToggle = (key: string) => {
    setFlags(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
    setSuccess(false);
  };

  const saveFlags = async () => {
    setSaving(true);
    try {
      const res = await fetch('http://localhost:7860/settings/feature-flags', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'dev-key-123'
        },
        body: JSON.stringify(flags)
      });
      if (res.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      console.error('Failed to save flags', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Loading feature flags...</div>;

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold tracking-tight text-white mb-2">Feature Flag Manager</h1>
          <p className="text-slate-400">Manage system capabilities and experimental features.</p>
        </div>
        <Button onClick={saveFlags} disabled={saving} className="bg-cyan-500 hover:bg-cyan-600 text-black">
          {saving ? 'Saving...' : success ? <><CheckCircle2 className="mr-2 h-4 w-4" /> Saved</> : <><Save className="mr-2 h-4 w-4" /> Save Changes</>}
        </Button>
      </div>

      <Card className="border-slate-800 bg-slate-900/50 backdrop-blur-xl">
        <CardHeader>
          <CardTitle className="text-xl">Safety & Compliance Flags</CardTitle>
          <CardDescription>Features that directly affect NFPA 72 compliance and deterministic results.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          <div className="flex items-center justify-between p-4 rounded-lg border border-slate-800 bg-slate-900/80">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">SMOKE_SIMULATION</span>
                <Badge variant="destructive" className="bg-red-500/20 text-red-400 border-red-500/30">Disabled by V8</Badge>
              </div>
              <p className="text-sm text-slate-400">CFD smoke spread simulation. Produces non-reproducible results violating audit trails.</p>
            </div>
            <Switch 
              checked={flags['SMOKE_SIMULATION'] || false} 
              onCheckedChange={() => handleToggle('SMOKE_SIMULATION')}
            />
          </div>

          <div className="flex items-center justify-between p-4 rounded-lg border border-slate-800 bg-slate-900/80">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">SELF_LEARNING</span>
                <Badge variant="destructive" className="bg-red-500/20 text-red-400 border-red-500/30">Disabled by V8</Badge>
              </div>
              <p className="text-sm text-slate-400">ML-based pattern learning. Learned patterns cannot be verified against NFPA 72.</p>
            </div>
            <Switch 
              checked={flags['SELF_LEARNING'] || false} 
              onCheckedChange={() => handleToggle('SELF_LEARNING')}
            />
          </div>

        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/50 backdrop-blur-xl">
        <CardHeader>
          <CardTitle className="text-xl">Integration & Analysis Flags</CardTitle>
          <CardDescription>Standard system capabilities and third-party bridges.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          
          {Object.entries(flags)
            .filter(([key]) => key !== 'SMOKE_SIMULATION' && key !== 'SELF_LEARNING')
            .map(([key, value]) => (
            <div key={key} className="flex items-center justify-between p-4 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-800/60 transition-colors">
              <div className="space-y-1">
                <span className="font-semibold text-white">{key}</span>
                <p className="text-sm text-slate-500">Toggle {key.toLowerCase().replace('_', ' ')} capabilities.</p>
              </div>
              <Switch 
                checked={value} 
                onCheckedChange={() => handleToggle(key)}
              />
            </div>
          ))}

        </CardContent>
      </Card>
    </div>
  );
}
