import React, { useState } from 'react';
import { BarChart3, ChevronDown, ChevronUp, Download, FileQuestion, Film, Headphones, Image, Loader2, Network, Presentation, Rows3, SquareStack } from 'lucide-react';
import type { ApiConfig, GeneratedContent } from '../App';
import { translations, useLanguage } from '../App';
import { ArtifactViewer } from './ArtifactViewer';

interface StudioPanelProps {
    sourceIds: string[];
    config: ApiConfig;
    contents: GeneratedContent[];
    onContentGenerated: (content: GeneratedContent) => void;
    onOpenSlideDeck: (deckId: string | null) => void;
}

const TOOLS = [
    { id: 'podcast', icon: Headphones, labelKey: 'podcast', styleClass: 'tool-podcast' },
    { id: 'mind_map', icon: Network, labelKey: 'mindmap', styleClass: 'tool-mindmap' },
    { id: 'ppt_outline', icon: Presentation, labelKey: 'ppt', styleClass: 'tool-ppt' },
    { id: 'faq', icon: FileQuestion, labelKey: 'faq', styleClass: 'tool-faq' },
    { id: 'flashcards', icon: SquareStack, labelKey: 'flashcards', styleClass: 'tool-cards' },
    { id: 'report', icon: Rows3, labelKey: 'report', styleClass: 'tool-report' },
    { id: 'data_table', icon: BarChart3, labelKey: 'table', styleClass: 'tool-table' },
    { id: 'video_overview', icon: Film, labelKey: 'video', styleClass: 'tool-video' },
    { id: 'infographic', icon: Image, labelKey: 'infographic', styleClass: 'tool-infographic' }
];

export const StudioPanel: React.FC<StudioPanelProps> = ({ sourceIds, config, contents, onContentGenerated, onOpenSlideDeck }) => {
    const { lang } = useLanguage();
    const t = translations[lang];
    const [activeTool, setActiveTool] = useState<string>('podcast');
    const [duration, setDuration] = useState('5-10');
    const [language, setLanguage] = useState('zh');
    const [count, setCount] = useState('6');
    const [difficulty, setDifficulty] = useState('standard');
    const [style, setStyle] = useState('overview');
    const [detail, setDetail] = useState('standard');
    const [customPrompt, setCustomPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const selectTool = (toolId: string) => {
        if (toolId === 'ppt_outline') {
            if (sourceIds.length === 0) {
                alert(lang === 'zh' ? '请先选择来源' : 'Select sources first.');
                return;
            }
            onOpenSlideDeck(null);
            return;
        }
        if (toolId === 'video_overview') {
            alert(lang === 'zh' ? '视频概览功能开发中' : 'Video Overview is under development.');
            return;
        }
        setActiveTool(toolId);
    };

    const generateArtifact = async () => {
        if (sourceIds.length === 0) return alert(lang === 'zh' ? '请先选择来源' : 'Select sources first.');
        setIsGenerating(true);
        try {
            if (activeTool === 'podcast') {
                const response = await fetch('/api/podcast/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_ids: sourceIds,
                        duration_range: duration,
                        llm_provider: config.textProvider,
                        llm_api_key: config.textApiKey,
                        llm_base_url: config.textBaseUrl || undefined,
                        llm_model: config.textModel || undefined
                    })
                });
                if (!response.ok) throw new Error(await response.text());
                const data = await response.json();
                onContentGenerated({
                    id: crypto.randomUUID(),
                    type: 'podcast',
                    title: lang === 'zh' ? '播客脚本' : 'Podcast Script',
                    createdAt: new Date(),
                    audioUrl: data.audio_url,
                    transcript: data.transcript,
                    markdown: data.transcript
                });
            } else {
                const response = await fetch('/api/artifacts/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        artifact_type: activeTool,
                        source_ids: sourceIds,
                        instruction: buildInstruction()
                    })
                });
                if (!response.ok) throw new Error(await response.text());
                const artifact = await response.json();
                onContentGenerated({
                    id: artifact.id,
                    type: artifact.artifact_type,
                    title: artifact.title,
                    createdAt: new Date(artifact.created_at),
                    markdown: artifact.markdown,
                    payload: artifact.payload,
                    downloadJsonUrl: `/api/artifacts/${artifact.id}/download?format=json`,
                    downloadMarkdownUrl: `/api/artifacts/${artifact.id}/download?format=markdown`,
                    downloadSvgUrl: artifact.artifact_type === 'infographic' ? `/api/artifacts/${artifact.id}/download?format=svg` : undefined
                });
            }
        } catch (e: any) {
            alert(e.message || 'Generation failed');
        } finally {
            setIsGenerating(false);
        }
    };

    const durationOptions = [
        { value: '3-5', label: '3-5' },
        { value: '5-10', label: '5-10' },
        { value: '10-15', label: '10-15' },
        { value: '15-20', label: '15-20' },
        { value: '20-30', label: '20-30' }
    ];

    const buildInstruction = () => {
        return [
            `language: ${language}`,
            `count: ${count}`,
            `difficulty: ${difficulty}`,
            `style: ${style}`,
            `detail: ${detail}`,
            customPrompt.trim() ? `custom_prompt: ${customPrompt.trim()}` : ''
        ].filter(Boolean).join('\n');
    };

    return (
        <>
            <div className="panel-header">
                <h2>{t.studio}</h2>
            </div>
            <div className="panel-body">
                <div className="tool-btn-grid">
                    {TOOLS.map(tool => {
                        const Icon = tool.icon;
                        const active = activeTool === tool.id;
                        return (
                            <button key={tool.id} onClick={() => selectTool(tool.id)} className={`tool-btn tool-card ${tool.styleClass} ${active ? 'active' : ''}`}>
                                <span className="tool-icon-wrap"><Icon size={19} /></span>
                                <span>{t.tools[tool.labelKey as keyof typeof t.tools]}</span>
                            </button>
                        );
                    })}
                </div>

                {activeTool === 'podcast' && (
                    <div className="podcast-duration-grid my-4">
                        {durationOptions.map(option => (
                            <button key={option.value} onClick={() => setDuration(option.value)} className={`duration-btn ${duration === option.value ? 'active' : ''}`}>
                                {option.label}
                            </button>
                        ))}
                    </div>
                )}

                {activeTool !== 'podcast' && (
                    <div className="studio-options">
                        <label>
                            <span>{lang === 'zh' ? '语言' : 'Language'}</span>
                            <select value={language} onChange={event => setLanguage(event.target.value)}>
                                <option value="zh">中文</option>
                                <option value="en">English</option>
                                <option value="source">Source</option>
                            </select>
                        </label>
                        <label>
                            <span>{activeTool === 'data_table' ? (lang === 'zh' ? '行数' : 'Rows') : (lang === 'zh' ? '数量' : 'Count')}</span>
                            <input value={count} onChange={event => setCount(event.target.value)} inputMode="numeric" />
                        </label>
                        <label>
                            <span>{lang === 'zh' ? '难度' : 'Difficulty'}</span>
                            <select value={difficulty} onChange={event => setDifficulty(event.target.value)}>
                                <option value="quick">{lang === 'zh' ? '快速' : 'Quick'}</option>
                                <option value="standard">{lang === 'zh' ? '标准' : 'Standard'}</option>
                                <option value="advanced">{lang === 'zh' ? '进阶' : 'Advanced'}</option>
                            </select>
                        </label>
                        <label>
                            <span>{lang === 'zh' ? '风格' : 'Style'}</span>
                            <select value={style} onChange={event => setStyle(event.target.value)}>
                                <option value="overview">{lang === 'zh' ? '概览' : 'Overview'}</option>
                                <option value="study_guide">{lang === 'zh' ? '学习指南' : 'Study guide'}</option>
                                <option value="briefing">{lang === 'zh' ? '简报' : 'Briefing'}</option>
                            </select>
                        </label>
                        <label>
                            <span>{lang === 'zh' ? '详细度' : 'Detail'}</span>
                            <select value={detail} onChange={event => setDetail(event.target.value)}>
                                <option value="concise">{lang === 'zh' ? '简洁' : 'Concise'}</option>
                                <option value="standard">{lang === 'zh' ? '标准' : 'Standard'}</option>
                                <option value="deep">{lang === 'zh' ? '深入' : 'Deep'}</option>
                            </select>
                        </label>
                        <label className="wide">
                            <span>{lang === 'zh' ? '自定义要求' : 'Custom prompt'}</span>
                            <textarea value={customPrompt} onChange={event => setCustomPrompt(event.target.value)} />
                        </label>
                    </div>
                )}

                <button onClick={generateArtifact} disabled={isGenerating || sourceIds.length === 0} className="primary-btn w-full my-4">
                    {isGenerating ? <Loader2 size={17} className="animate-spin" /> : null}
                    {activeTool === 'podcast' ? t.generatePodcast : (lang === 'zh' ? '生成' : 'Generate')}
                </button>

                <h3 className="text-sm font-bold text-gray-800 mb-3">{t.generatedContent}</h3>
                {contents.length === 0 && (
                    <div className="p-6 border border-dashed border-gray-200 rounded-lg text-center bg-white/50">
                        <p className="text-sm text-gray-400">{t.noContent}</p>
                    </div>
                )}
                {contents.map(content => (
                    <div key={content.id} className="artifact-card">
                        <button
                            className="artifact-head"
                            onClick={() => {
                                if (content.type === 'slide_deck' && typeof content.payload?.deck_id === 'string') {
                                    onOpenSlideDeck(content.payload.deck_id);
                                    return;
                                }
                                setExpandedId(expandedId === content.id ? null : content.id);
                            }}
                        >
                            <div>
                                <div className="text-sm font-semibold text-gray-800">{content.title}</div>
                                <div className="text-[11px] text-gray-500">{content.type}</div>
                            </div>
                            {expandedId === content.id ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
                        </button>
                        {expandedId === content.id && (
                            <div className="artifact-body">
                                {content.audioUrl && <audio controls src={content.audioUrl} className="w-full mb-3" />}
                                <ArtifactViewer content={content} />
                                <div className="flex gap-2 mt-3">
                                    {content.downloadMarkdownUrl && <a className="secondary-btn" href={content.downloadMarkdownUrl}><Download size={14} /> Markdown</a>}
                                    {content.downloadJsonUrl && <a className="secondary-btn" href={content.downloadJsonUrl}><Download size={14} /> JSON</a>}
                                    {content.downloadSvgUrl && <a className="secondary-btn" href={content.downloadSvgUrl}><Download size={14} /> SVG</a>}
                                    {content.audioUrl && <a className="secondary-btn" href={content.audioUrl}><Download size={14} /> MP3</a>}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </>
    );
};
