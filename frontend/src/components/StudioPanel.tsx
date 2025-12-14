import React, { useState } from 'react';
import {
    Mic, FileText, Image, Video, Presentation,
    Play, Pause, Download, Loader2, Clock, ChevronDown, ChevronUp,
    Headphones, MoreHorizontal
} from 'lucide-react';
import type { ApiConfig, GeneratedContent } from '../App';

interface StudioPanelProps {
    documentIds: string[];
    config: ApiConfig;
    contents: GeneratedContent[];
    onContentGenerated: (content: GeneratedContent) => void;
}

const DURATION_OPTIONS = [
    { value: '3-5', label: '3-5 分钟', desc: '简短' },
    { value: '5-10', label: '5-10 分钟', desc: '标准' },
    { value: '10-15', label: '10-15 分钟', desc: '详细' },
    { value: '15-20', label: '15-20 分钟', desc: '深度' },
];

const TOOLS = [
    { id: 'podcast', icon: Headphones, label: '音频概述', color: 'from-orange-400 to-red-400', available: true },
    { id: 'summary', icon: FileText, label: '摘要导图', color: 'from-blue-400 to-indigo-400', available: false },
    { id: 'ppt', icon: Presentation, label: '演示文档', color: 'from-green-400 to-teal-400', available: false },
    { id: 'faq', icon: FileText, label: '常见问答', color: 'from-purple-400 to-pink-400', available: false },
];

export const StudioPanel: React.FC<StudioPanelProps> = ({
    documentIds,
    config,
    contents,
    onContentGenerated
}) => {
    const [activeTool, setActiveTool] = useState<string | null>(null);
    const [duration, setDuration] = useState('5-10');
    const [isGenerating, setIsGenerating] = useState(false);
    const [playingId, setPlayingId] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const handleGeneratePodcast = async () => {
        if (documentIds.length === 0) {
            alert('请先上传文档');
            return;
        }
        if (!config.textApiKey) {
            alert('请先配置文本模型 API Key');
            return;
        }

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
                    llm_model: config.textModel,
                    tts_provider: config.speechProvider,
                    tts_api_key: config.speechApiKey || config.textApiKey
                })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || '生成失败');
            }

            const data = await response.json();
            onContentGenerated({
                id: Date.now().toString(),
                type: 'podcast',
                title: `播客 - ${new Date().toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`,
                createdAt: new Date(),
                audioUrl: data.audio_url,
                transcript: data.transcript
            });
            setActiveTool(null);
        } catch (err: any) {
            alert(err.message || '生成失败');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDownload = async (audioUrl: string, title: string) => {
        try {
            const response = await fetch(audioUrl);
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${title}.mp3`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert('下载失败');
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--border-light)]">
                <h2 className="font-semibold text-[var(--warm-800)]">Studio</h2>
                <button className="p-1.5 hover:bg-[var(--bg-hover)] rounded-lg transition-colors">
                    <MoreHorizontal className="w-4 h-4 text-[var(--warm-400)]" />
                </button>
            </div>

            {/* Tools Grid */}
            <div className="p-4 border-b border-[var(--border-light)]">
                <div className="tool-grid">
                    {TOOLS.map((tool) => {
                        const Icon = tool.icon;
                        return (
                            <button
                                key={tool.id}
                                onClick={() => tool.available && setActiveTool(activeTool === tool.id ? null : tool.id)}
                                disabled={!tool.available}
                                className={`tool-btn ${activeTool === tool.id ? 'active' : ''} ${!tool.available ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${tool.color} flex items-center justify-center mb-1`}>
                                    <Icon className="w-4 h-4 text-white" />
                                </div>
                                <span>{tool.label}</span>
                                {!tool.available && <span className="text-[8px] text-[var(--warm-400)]">即将推出</span>}
                            </button>
                        );
                    })}
                </div>

                {/* Podcast Options */}
                {activeTool === 'podcast' && (
                    <div className="mt-4 p-4 bg-[var(--warm-50)] rounded-xl fade-in">
                        <label className="label">播客时长</label>
                        <div className="grid grid-cols-2 gap-2 mb-4">
                            {DURATION_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    onClick={() => setDuration(opt.value)}
                                    className={`p-2 rounded-lg text-left transition-all ${duration === opt.value
                                            ? 'bg-gradient-to-br from-amber-400 to-orange-500 text-white'
                                            : 'bg-white border border-[var(--border-light)] hover:border-[var(--primary-300)]'
                                        }`}
                                >
                                    <div className="text-sm font-medium">{opt.label}</div>
                                    <div className={`text-xs ${duration === opt.value ? 'text-white/80' : 'text-[var(--warm-400)]'}`}>
                                        {opt.desc}
                                    </div>
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={handleGeneratePodcast}
                            disabled={isGenerating || documentIds.length === 0}
                            className="btn btn-primary w-full"
                        >
                            {isGenerating ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                    生成中...
                                </>
                            ) : (
                                <>
                                    <Mic className="w-4 h-4 mr-2" />
                                    生成播客
                                </>
                            )}
                        </button>
                    </div>
                )}
            </div>

            {/* Generated Contents */}
            <div className="flex-1 overflow-y-auto p-4">
                <h3 className="text-xs font-medium text-[var(--warm-500)] uppercase tracking-wider mb-3">
                    生成内容
                </h3>

                {contents.length === 0 ? (
                    <div className="text-center py-8 text-[var(--warm-400)]">
                        <Headphones className="w-10 h-10 mx-auto mb-2 opacity-30" />
                        <p className="text-sm">暂无生成内容</p>
                        <p className="text-xs mt-1">选择工具开始创建</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {contents.map((content) => (
                            <div key={content.id} className="output-card">
                                <div
                                    className="output-card-header cursor-pointer"
                                    onClick={() => setExpandedId(expandedId === content.id ? null : content.id)}
                                >
                                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-400 to-red-400 flex items-center justify-center mr-3">
                                        <Headphones className="w-4 h-4 text-white" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-[var(--warm-800)] truncate">
                                            {content.title}
                                        </p>
                                        <p className="text-xs text-[var(--warm-400)]">
                                            {content.createdAt.toLocaleString('zh-CN', {
                                                month: 'short', day: 'numeric',
                                                hour: '2-digit', minute: '2-digit'
                                            })}
                                        </p>
                                    </div>
                                    {expandedId === content.id ? (
                                        <ChevronUp className="w-4 h-4 text-[var(--warm-400)]" />
                                    ) : (
                                        <ChevronDown className="w-4 h-4 text-[var(--warm-400)]" />
                                    )}
                                </div>

                                {expandedId === content.id && content.audioUrl && (
                                    <div className="output-card-body fade-in">
                                        {/* Audio Player */}
                                        <div className="audio-player mb-3">
                                            <audio
                                                controls
                                                className="w-full"
                                                src={content.audioUrl}
                                            />
                                        </div>

                                        {/* Actions */}
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => handleDownload(content.audioUrl!, content.title)}
                                                className="btn btn-secondary flex-1"
                                            >
                                                <Download className="w-4 h-4 mr-2" />
                                                下载音频
                                            </button>
                                        </div>

                                        {/* Transcript Preview */}
                                        {content.transcript && (
                                            <div className="mt-3 p-3 bg-[var(--warm-50)] rounded-lg">
                                                <p className="text-xs font-medium text-[var(--warm-600)] mb-2">
                                                    📝 文字稿
                                                </p>
                                                <p className="text-xs text-[var(--warm-500)] line-clamp-4">
                                                    {content.transcript}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
