import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import { ShieldAlert, ShieldCheck } from 'lucide-react';

interface AuditEvent {
  hash: string;
  previous_hash: string;
  timestamp: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- d3 hierarchy requires any for dynamic node data
  data: Record<string, any>;
}

export const AuditVisualizer: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [chain, setChain] = useState<AuditEvent[]>([]);
  const [verifyStatus, setVerifyStatus] = useState<{valid: boolean; message: string} | null>(null);

  useEffect(() => {
    // Fetch audit chain
    const fetchAudit = async () => {
      try {
        const [chainRes, verifyRes] = await Promise.all([
          fetch('http://localhost:8000/audit/chain', {
            headers: { 'X-API-Key': process.env.VITE_FIREAI_API_KEY || 'test-key' }
          }),
          fetch('http://localhost:8000/audit/verify', {
            headers: { 'X-API-Key': process.env.VITE_FIREAI_API_KEY || 'test-key' }
          })
        ]);
        
        if (chainRes.ok) setChain(await chainRes.json());
        if (verifyRes.ok) setVerifyStatus(await verifyRes.json());
      } catch (err) {
        console.error("Failed to fetch audit data", err);
      }
    };
    fetchAudit();
  }, []);

  useEffect(() => {
    if (!chain.length || !svgRef.current || !wrapperRef.current) return;

    // Convert linear chain to hierarchy for D3
    /* eslint-disable @typescript-eslint/no-explicit-any -- d3.hierarchy datum must be any for dynamic property access */
    const hierarchyData: Record<string, any> = { ...chain[0], name: (chain[0].data as Record<string, any>).event as string || 'GENESIS', children: [] as Record<string, any>[] };
    let current = hierarchyData;
    for (let i = 1; i < chain.length; i++) {
      const nodeData: Record<string, any> = { ...chain[i], name: (chain[i].data as Record<string, any>).event as string, children: [] as Record<string, any>[] };
      (current.children as Record<string, any>[]).push(nodeData);
      /* eslint-enable @typescript-eslint/no-explicit-any */
      current = nodeData;
    }

    const { width, height } = wrapperRef.current.getBoundingClientRect();
    
    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g').attr('transform', `translate(50, ${height / 2})`);

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 3])
      .on('zoom', (e) => {
        g.attr('transform', e.transform);
      });
      
    svg.call(zoom as unknown as (selection: d3.Selection<SVGSVGElement, unknown, null, undefined>) => void);

    // Tree layout (horizontal chain)
    // Note: tree() uses nodeSize to spread things out.
    // For a simple chain, d3.tree() is a bit overkill but satisfying visually.
    const tree = d3.tree().nodeSize([100, 200]);
    const root = d3.hierarchy(hierarchyData);
    // @ts-expect-error -- d3.tree() return type has incompatible generics with d3.hierarchy() for any-typed data
    tree(root);

    // Swap x and y for horizontal layout
    root.each((d) => {
      const temp = d.x;
      d.x = d.y;
      d.y = temp;
    });

    // Draw Links
    g.selectAll('.link')
      .data(root.links())
      .join('path')
      .attr('class', 'link')
      .attr('fill', 'none')
      .attr('stroke', 'hsl(var(--muted-foreground))')
      .attr('stroke-width', 2)
      /* eslint-disable @typescript-eslint/no-explicit-any -- d3.linkHorizontal() typing is incompatible with d3.tree() output */
      .attr('d', d3.linkHorizontal<any, any>()
        .x((d: any) => d.x)
        .y((d: any) => d.y) as unknown as string);
      /* eslint-enable @typescript-eslint/no-explicit-any */

    // Draw Nodes
    const node = g.selectAll('.node')
      .data(root.descendants())
      .join('g')
      .attr('class', 'node')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- d3 HierarchyNode generic typing
      .attr('transform', (d: any) => `translate(${d.x},${d.y})`);

    node.append('circle')
      .attr('r', 10)
      .attr('fill', verifyStatus?.valid ? 'hsl(var(--primary))' : 'hsl(var(--destructive))');

    node.append('text')
      .attr('dy', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', 'currentColor')
      .attr('class', 'text-xs font-semibold')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- d3 HierarchyNode generic typing
      .text((d: any) => d.data.name as string);
      
    node.append('text')
      .attr('dy', 25)
      .attr('text-anchor', 'middle')
      .attr('fill', 'currentColor')
      .attr('class', 'text-[10px] opacity-70')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- d3 HierarchyNode generic typing
      .text((d: any) => (d.data.hash as string)?.substring(0, 8) ?? null);

  }, [chain, verifyStatus]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle>Merkle Tree Audit Visualizer</CardTitle>
        <CardDescription>Cryptographic tamper-evident trail of all engineering decisions (NFPA 72 §10.6)</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 min-h-[400px]">
        {verifyStatus && (
          <Alert variant={verifyStatus.valid ? "default" : "destructive"} className="shrink-0">
            {verifyStatus.valid ? <ShieldCheck className="h-4 w-4 text-primary" /> : <ShieldAlert className="h-4 w-4" />}
            <AlertTitle>{verifyStatus.valid ? "Integrity Verified" : "INTEGRITY COMPROMISED"}</AlertTitle>
            <AlertDescription>{verifyStatus.message}</AlertDescription>
          </Alert>
        )}
        <div ref={wrapperRef} className="flex-1 bg-muted/20 rounded-md overflow-hidden border">
          <svg ref={svgRef} className="w-full h-full" />
        </div>
      </CardContent>
    </Card>
  );
};
