import React, { useEffect, useState } from 'react';
import { Activity, Cpu, HardDrive, Wifi } from 'lucide-react';

export const SystemStatus: React.FC = () => {
    const [metrics, setMetrics] = useState({
        cpu: 12,
        memory: 45,
        network: 120,
        latency: 24
    });

    useEffect(() => {
        const interval = setInterval(() => {
            setMetrics({
                cpu: Math.floor(Math.random() * 30) + 10,
                memory: Math.floor(Math.random() * 20) + 40,
                network: Math.floor(Math.random() * 500) + 100,
                latency: Math.floor(Math.random() * 10) + 20
            });
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="glass-panel rounded-xl p-6 border border-slate-700/50 bg-slate-900/80 tech-border">
            <div className="flex items-center justify-between mb-6 border-b border-slate-700 pb-3">
                <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-widest flex items-center">
                    <Activity className="w-4 h-4 mr-2" />
                    System Metrics
                </h3>
                <span className="text-xs text-emerald-400 animate-pulse font-bold">● ONLINE</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                    <div className="flex items-center text-slate-400 text-xs">
                        <Cpu className="w-3 h-3 mr-1" /> CPU Load
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-cyan-500 transition-all duration-500"
                            style={{ width: `${metrics.cpu}%` }}
                        />
                    </div>
                    <div className="text-right text-[10px] text-cyan-300 font-mono">{metrics.cpu}%</div>
                </div>

                <div className="space-y-1">
                    <div className="flex items-center text-slate-400 text-xs">
                        <HardDrive className="w-3 h-3 mr-1" /> Memory
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-purple-500 transition-all duration-500"
                            style={{ width: `${metrics.memory}%` }}
                        />
                    </div>
                    <div className="text-right text-[10px] text-purple-300 font-mono">{metrics.memory}%</div>
                </div>

                <div className="space-y-1">
                    <div className="flex items-center text-slate-400 text-xs">
                        <Wifi className="w-3 h-3 mr-1" /> Network
                    </div>
                    <div className="text-xs font-mono text-slate-300">
                        {metrics.network} <span className="text-slate-600">KB/s</span>
                    </div>
                </div>

                <div className="space-y-1">
                    <div className="flex items-center text-slate-400 text-xs">
                        <Activity className="w-3 h-3 mr-1" /> Latency
                    </div>
                    <div className="text-xs font-mono text-emerald-400">
                        {metrics.latency} <span className="text-slate-600">ms</span>
                    </div>
                </div>
            </div>

            <div className="mt-4 pt-2 border-t border-slate-800">
                <div className="text-[10px] text-slate-600 font-mono uppercase">
                    &gt; System Ready<br />
                    &gt; Waiting for input...
                </div>
            </div>
        </div>
    );
};
