import React, { useState } from 'react';
import { Headphones, Network, Presentation, HelpCircle, Mic, Download, Loader2, Play, ChevronDown, ChevronUp } from 'lucide-react';
import type { ApiConfig, GeneratedContent } from '../App';
import { useLanguage, translations } from '../App';

interface StudioPanelProps {
    documentIds: string[];
    config: ApiConfig;
    contents: GeneratedContent[];
    onContentGenerated: (content: GeneratedContent) => void;
}

// Tool definitions with gradient colors
const TOOLS = [
    { id: 'podcast', icon: Headphones, labelKey: 'podcast', gradient: 'from-blue-400 to-indigo-500', shadow: 'shadow-blue-200', available: true },
    { id: 'mindmap', icon: Network, labelKey: 'mindmap', gradient: 'from-emerald-400 to-teal-500', shadow: 'shadow-emerald-200', available: false },
    { id: 'ppt', icon: Presentation, labelKey: 'ppt', gradient: 'from-rose-400 to-pink-500', shadow: 'shadow-pink-200', available: false },
    { id: 'faq', icon: HelpCircle, labelKey: 'faq', gradient: 'from-amber-400 to-orange-500', shadow: 'shadow-orange-200', available: false },
];

export const StudioPanel: React.FC<StudioPanelProps> = ({ documentIds, config, contents, onContentGenerated }) => {
    const { lang } = useLanguage();
    const t = translations[lang];

    const [activeTool, setActiveTool] = useState<string | null>(null);
    const [duration, setDuration] = useState('5-10');
    const [isGenerating, setIsGenerating] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const handleGeneratePodcast = async () => {
        if (documentIds.length === 0) return alert('No documents to process');
        if (!config.textApiKey) return alert('Configure API Key first');

        setIsGenerating(true);
        try {
            const response = await fetch('/api/podcast/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_ids: documentIds,
                    duration_range: duration,
                    prompt_type: 'default',
                    host_voice: 'alloy',
                    guest_voice: 'nova',
                    llm_provider: config.textProvider,
                    llm_api_key: config.textApiKey,
                    llm_base_url: config.textBaseUrl || undefined,
                    llm_model: config.textModel || undefined,
                    tts_provider: config.speechProvider,
                    tts_api_key: config.speechApiKey || config.textApiKey,
                    tts_base_url: config.speechBaseUrl || undefined,
                    tts_model: config.speechModel || undefined
                })
            });

            if (!response.ok) throw new Error('Generation failed');
            const data = await response.json();

            onContentGenerated({
                id: Date.now().toString(),
                type: 'podcast',
                title: lang === 'zh' ? '音频摘要：项目提案' : 'Audio Summary: Project Proposal',
                createdAt: new Date(),
                audioUrl: data.audio_url,
                transcript: data.transcript
            });
            setActiveTool(null);
        } catch (e: any) {
            alert(e.message || 'Error generating podcast');
        } finally {
            setIsGenerating(false);
        }
    };

    const durationOptions = [
        { value: '3-5', label: '3-5 min', desc: t.quick },
        { value: '5-10', label: '5-10 min', desc: t.standard },
        { value: '10-15', label: '10-15 min', desc: t.detailed },
        { value: '15-20', label: '15-20 min', desc: t.deepDive }
    ];

    return (
        <>
            <div className="panel-header">
                <h2>{t.studio}</h2>
            </div>

            <div className="panel-body">
                {/* Tool Grid - All Colorful */}
                <div className="grid grid-cols-2 gap-3 p-1 mb-6">
                    {TOOLS.map((tool) => {
                        const Icon = tool.icon;
                        const label = t.tools[tool.labelKey as keyof typeof t.tools];
                        const isActive = activeTool === tool.id;

                        return (
                            <button
                                key={tool.id}
                                onClick={() => tool.available && setActiveTool(isActive ? null : tool.id)}
                                className={`
                                    group relative overflow-hidden h-24 rounded-2xl p-4 flex flex-col justify-between 
                                    bg-gradient-to-br ${tool.gradient} 
                                    text-white shadow-lg ${tool.shadow} 
                                    transition-all duration-300 hover:scale-[1.02] hover:shadow-xl active:scale-95
                                    ${!tool.available ? 'opacity-70' : ''}
                                `}
                                style={isActive ? { boxShadow: '0 0 0 4px #f59e0b, 0 10px 15px -3px rgba(0, 0, 0, 0.1)' } : {}}
                            >
                                {/* Decorative Circle */}
                                <div className="absolute top-0 right-0 w-16 h-16 bg-white opacity-10 rounded-full -mr-8 -mt-8 blur-lg" />

                                {/* Icon */}
                                <div className="bg-white/20 w-fit p-2 rounded-xl backdrop-blur-md shadow-inner group-hover:bg-white/30 transition-colors">
                                    <Icon size={20} />
                                </div>

                                {/* Label */}
                                <p className="font-bold text-sm tracking-wide">{label}</p>
                            </button>
                        );
                    })}
                </div>

                {/* Podcast Options */}
                {activeTool === 'podcast' && (
                    <div className="mb-6 p-4 bg-white rounded-2xl border border-gray-100 shadow-sm animate-fade-in">
                        <label className="text-xs font-bold text-gray-500 uppercase tracking-wider block mb-3">{t.duration}</label>
                        <div className="grid grid-cols-2 gap-2 mb-4">
                            {durationOptions.map(d => (
                                <button
                                    key={d.value}
                                    onClick={() => setDuration(d.value)}
                                    className={`py-2.5 px-3 text-left rounded-xl border transition-all ${duration === d.value
                                        ? 'bg-gradient-to-r from-amber-500 to-orange-500 border-transparent text-white shadow-md'
                                        : 'border-gray-200 text-gray-600 hover:bg-gray-50 bg-white'}`}
                                >
                                    <div className="text-sm font-semibold">{d.label}</div>
                                    <div className={`text-[10px] ${duration === d.value ? 'text-white/80' : 'text-gray-400'}`}>{d.desc}</div>
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={handleGeneratePodcast}
                            disabled={isGenerating}
                            className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white font-semibold text-sm shadow-lg shadow-orange-500/20 hover:shadow-xl transition-all flex items-center justify-center gap-2"
                        >
                            {isGenerating ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} />}
                            {t.generatePodcast}
                        </button>
                    </div>
                )}

                {/* Generated Content Section */}
                <div>
                    <h3 className="text-sm font-bold text-gray-800 mb-3">{t.generatedContent}</h3>

                    {contents.length === 0 && (
                        <div className="p-6 border border-dashed border-gray-200 rounded-xl text-center bg-white/50">
                            <p className="text-sm text-gray-400">{t.noContent}</p>
                        </div>
                    )}

                    {contents.map((content) => (
                        <div key={content.id} className="bg-white rounded-2xl p-4 mb-3 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                            <div
                                className="flex items-center justify-between cursor-pointer"
                                onClick={() => setExpandedId(expandedId === content.id ? null : content.id)}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center">
                                        <Headphones size={20} />
                                    </div>
                                    <div>
                                        <div className="text-sm font-semibold text-gray-800">{content.title}</div>
                                        <div className="text-[11px] text-gray-400">
                                            {content.createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    </div>
                                </div>
                                {expandedId === content.id ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
                            </div>

                            {expandedId === content.id && content.audioUrl && (
                                <div className="mt-4 animate-fade-in">
                                    <div className="bg-orange-50 rounded-xl p-3 flex items-center gap-3 border border-orange-100">
                                        <button className="w-10 h-10 bg-orange-600 rounded-full flex items-center justify-center text-white shadow-md hover:bg-orange-700 transition">
                                            <Play size={16} className="ml-0.5" fill="currentColor" />
                                        </button>
                                        {/* Waveform */}
                                        <div className="flex-1 flex items-center gap-[2px] h-8 overflow-hidden">
                                            {[...Array(20)].map((_, i) => (
                                                <div key={i} className="w-1 bg-orange-300 rounded-full" style={{ height: `${30 + Math.random() * 70}%` }} />
                                            ))}
                                        </div>
                                        <span className="text-xs font-semibold text-orange-700">5:30</span>
                                    </div>

                                    <p className="mt-3 text-xs text-gray-600 leading-relaxed line-clamp-2">
                                        {content.transcript || (lang === 'zh' ? '关于项目目标、策略和预算的简明音频概述。' : 'A concise audio overview of the project goals, strategy, and budget.')}
                                    </p>

                                    <button className="mt-3 w-full py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 flex items-center justify-center gap-2">
                                        <Download size={16} /> Download
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
};
