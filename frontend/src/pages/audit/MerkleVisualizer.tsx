import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';

interface AuditNode {
  hash: string;
  previous_hash: string;
  timestamp: string;
  data: Record<string, any>;
}

export function MerkleVisualizer() {
  const [chain, setChain] = useState<AuditNode[]>([]);
  const [loading, setLoading] = useState(true);

  // In a real app, this would fetch from FastAPI
  useEffect(() => {
    // Mocking an audit chain response for the UI demonstration
    setTimeout(() => {
      setChain([
        {
          hash: 'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3',
          previous_hash: 'GENESIS',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          data: { event: 'SYSTEM_STARTUP', message: 'Audit chain initialized' }
        },
        {
          hash: 'b6589fc6ab0dc82cf12099d1c2d40ab994e8410c',
          previous_hash: 'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3',
          timestamp: new Date(Date.now() - 1800000).toISOString(),
          data: { event: 'FEATURE_FLAG_CHANGE', flag: 'RESILIENCE_CHECK', state: false }
        },
        {
          hash: '356a192b7913b04c54574d18c28d46e6395428ab',
          previous_hash: 'b6589fc6ab0dc82cf12099d1c2d40ab994e8410c',
          timestamp: new Date().toISOString(),
          data: { event: 'DESIGN_COMPLIANCE_PASS', project_id: 'PRJ-8821' }
        }
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  if (loading) return <div className="p-8 text-center">Loading Merkle Chain...</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold tracking-tight text-white mb-2">Audit Merkle Tree</h1>
          <p className="text-slate-400">Cryptographically verifiable log of all compliance and system changes.</p>
        </div>
        <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 px-3 py-1">
          <ShieldCheck className="w-4 h-4 mr-2" />
          Chain Integrity Valid
        </Badge>
      </div>

      <div className="space-y-4">
        {chain.map((node, i) => (
          <div key={node.hash} className="relative">
            {/* Connecting Line */}
            {i !== chain.length - 1 && (
              <div className="absolute left-[23px] top-[48px] bottom-[-24px] w-0.5 bg-slate-800 z-0"></div>
            )}
            
            <Card className="relative z-10 border-slate-800 bg-slate-900/50 backdrop-blur-xl">
              <CardContent className="p-4 flex items-start gap-4">
                <div className="mt-1 flex-shrink-0">
                  <div className="w-4 h-4 rounded-full bg-cyan-500/20 border-2 border-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.3)]"></div>
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">{node.data.event}</span>
                    <span className="text-xs text-slate-500 font-mono">{new Date(node.timestamp).toLocaleString()}</span>
                  </div>
                  
                  <div className="bg-slate-950/50 rounded-md p-3 font-mono text-xs text-slate-400 overflow-x-auto border border-slate-800">
                    <div className="flex gap-4">
                      <span className="text-slate-500">Hash:</span>
                      <span className="text-cyan-400">{node.hash}</span>
                    </div>
                    <div className="flex gap-4">
                      <span className="text-slate-500">Prev:</span>
                      <span className="text-slate-600">{node.previous_hash}</span>
                    </div>
                    <div className="mt-2 text-emerald-400/80">
                      {JSON.stringify(node.data, null, 2)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ))}
      </div>
    </div>
  );
}
