import React, { createContext, useContext, useEffect, useState } from 'react';
import { Layers3, Moon, Settings, Sun } from 'lucide-react';
import { SourcePanel } from './components/SourcePanel';
import { ChatPanel } from './components/ChatPanel';
import { StudioPanel } from './components/StudioPanel';
import { ConfigModal } from './components/ConfigModal';
import { NotesPanel } from './components/NotesPanel';
import { SlideDeckWorkspace } from './components/SlideDeckWorkspace';

export type Language = 'zh' | 'en';
export const LanguageContext = createContext<{ lang: Language; setLang: (l: Language) => void }>({
    lang: 'zh',
    setLang: () => { }
});
export const useLanguage = () => useContext(LanguageContext);

export const translations = {
    zh: {
        sources: '来源',
        chat: '对话',
        studio: '工作室',
        generatedContent: '生成内容',
        searchPlaceholder: '搜索来源...',
        dragDropText: '上传文件或粘贴文本',
        startChat: '开始对话',
        inputPlaceholder: '基于选中来源提问...',
        noContent: '暂无生成内容',
        tools: {
            podcast: '播客',
            mindmap: '思维图谱',
            ppt: 'PPT',
            faq: 'FAQ',
            flashcards: '卡片',
            report: '报告',
            table: '表格',
            video: '视频概览',
            infographic: '信息图'
        },
        duration: '时长',
        generatePodcast: '生成播客',
        quick: '快速',
        standard: '标准',
        detailed: '详细',
        deepDive: '深度'
    },
    en: {
        sources: 'Sources',
        chat: 'Chat',
        studio: 'Studio',
        generatedContent: 'Artifacts',
        searchPlaceholder: 'Search sources...',
        dragDropText: 'Upload files or paste text',
        startChat: 'Start Chat',
        inputPlaceholder: 'Ask about selected sources...',
        noContent: 'No artifacts yet',
        tools: {
            podcast: 'Podcast',
            mindmap: 'Mind Map',
            ppt: 'PPT',
            faq: 'FAQ',
            flashcards: 'Cards',
            report: 'Report',
            table: 'Table',
            video: 'Video',
            infographic: 'Infographic'
        },
        duration: 'Duration',
        generatePodcast: 'Generate Podcast',
        quick: 'Quick',
        standard: 'Standard',
        detailed: 'Detailed',
        deepDive: 'Deep Dive'
    }
};

export interface ApiConfig {
    textProvider: 'litellm' | 'openai' | 'anthropic' | 'gemini';
    textApiKey: string;
    textApiKeySet: boolean;
    textBaseUrl: string;
    textModel: string;
    textThinking: 'enabled' | 'disabled';
    embeddingProvider: 'openai-compatible';
    embeddingApiKey: string;
    embeddingApiKeySet: boolean;
    embeddingBaseUrl: string;
    embeddingModel: string;
    rerankProvider: 'openai-compatible';
    rerankApiKey: string;
    rerankApiKeySet: boolean;
    rerankBaseUrl: string;
    rerankModel: string;
    speechProvider: 'openai-compatible';
    speechApiKey: string;
    speechApiKeySet: boolean;
    speechBaseUrl: string;
    speechModel: string;
    speechVoice: string;
    speechFormat: string;
    theme: 'light' | 'dark';
}

export interface SourceItem {
    id: string;
    kind: string;
    title: string;
    filename?: string;
    status: 'processing' | 'ready' | 'error' | 'deleted';
    error?: string;
    chunk_count: number;
    char_count: number;
    created_at: string;
}

export interface GeneratedContent {
    id: string;
    type: string;
    title: string;
    createdAt: Date;
    audioUrl?: string | null;
    transcript?: string;
    markdown?: string;
    payload?: Record<string, unknown>;
    downloadJsonUrl?: string;
    downloadMarkdownUrl?: string;
    downloadSvgUrl?: string;
}

function App() {
    const [lang, setLang] = useState<Language>('zh');
    const [sources, setSources] = useState<SourceItem[]>([]);
    const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
    const [generatedContents, setGeneratedContents] = useState<GeneratedContent[]>([]);
    const [notesRefreshKey, setNotesRefreshKey] = useState(0);
    const [showConfig, setShowConfig] = useState(false);
    const [slideDeckWorkspaceId, setSlideDeckWorkspaceId] = useState<string | null | undefined>(() => {
        return localStorage.getItem('notebooklm-active-slide-deck') || undefined;
    });
    const [config, setConfig] = useState<ApiConfig>({
        textProvider: 'litellm',
        textApiKey: '',
        textApiKeySet: false,
        textBaseUrl: '',
        textModel: '',
        textThinking: 'enabled',
        embeddingProvider: 'openai-compatible',
        embeddingApiKey: '',
        embeddingApiKeySet: false,
        embeddingBaseUrl: '',
        embeddingModel: '',
        rerankProvider: 'openai-compatible',
        rerankApiKey: '',
        rerankApiKeySet: false,
        rerankBaseUrl: '',
        rerankModel: '',
        speechProvider: 'openai-compatible',
        speechApiKey: '',
        speechApiKeySet: false,
        speechBaseUrl: '',
        speechModel: '',
        speechVoice: '',
        speechFormat: 'mp3',
        theme: (localStorage.getItem('notebooklm-theme') as 'light' | 'dark') || 'light'
    });

    const refreshSources = async () => {
        const response = await fetch('/api/sources');
        if (!response.ok) return;
        const data = await response.json();
        setSources(data.sources || []);
    };

    useEffect(() => {
        refreshSources();
        refreshArtifacts();
        loadRuntimeConfig();
    }, []);

    useEffect(() => {
        localStorage.setItem('notebooklm-theme', config.theme);
    }, [config.theme]);

    const profileToConfig = (current: ApiConfig, payload: any): ApiConfig => {
        const models = payload?.models || {};
        const text = models.text_model || {};
        const embedding = models.embedding_model || {};
        const rerank = models.rerank_model || {};
        const speech = models.audio_model || {};
        return {
            ...current,
            textApiKeySet: Boolean(text.api_key_set),
            textBaseUrl: text.base_url || current.textBaseUrl,
            textModel: text.model || current.textModel,
            textThinking: text.thinking?.type || current.textThinking,
            embeddingApiKeySet: Boolean(embedding.api_key_set),
            embeddingBaseUrl: embedding.base_url || current.embeddingBaseUrl,
            embeddingModel: embedding.model || current.embeddingModel,
            rerankApiKeySet: Boolean(rerank.api_key_set),
            rerankBaseUrl: rerank.base_url || current.rerankBaseUrl,
            rerankModel: rerank.model || current.rerankModel,
            speechApiKeySet: Boolean(speech.api_key_set),
            speechBaseUrl: speech.base_url || current.speechBaseUrl,
            speechModel: speech.model || current.speechModel,
            speechVoice: speech.voice || current.speechVoice,
            speechFormat: speech.response_format || current.speechFormat
        };
    };

    const loadRuntimeConfig = async () => {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) return;
            const payload = await response.json();
            setConfig(prev => profileToConfig(prev, payload));
        } catch {
            // The UI can still work with manually entered settings.
        }
    };

    const saveRuntimeConfig = async (nextConfig: ApiConfig) => {
        const payload = {
            models: {
                text_model: {
                    model: nextConfig.textModel,
                    base_url: nextConfig.textBaseUrl,
                    api_key: nextConfig.textApiKey,
                    adapter: `${nextConfig.textProvider}_chat`,
                    thinking: { type: nextConfig.textThinking }
                },
                embedding_model: {
                    model: nextConfig.embeddingModel,
                    base_url: nextConfig.embeddingBaseUrl,
                    api_key: nextConfig.embeddingApiKey,
                    adapter: 'openai_embedding'
                },
                rerank_model: {
                    model: nextConfig.rerankModel,
                    base_url: nextConfig.rerankBaseUrl,
                    api_key: nextConfig.rerankApiKey,
                    adapter: 'openai_rerank'
                },
                audio_model: {
                    model: nextConfig.speechModel,
                    base_url: nextConfig.speechBaseUrl,
                    api_key: nextConfig.speechApiKey,
                    voice: nextConfig.speechVoice,
                    response_format: nextConfig.speechFormat,
                    adapter: 'openai_speech',
                    stream: true
                }
            }
        };
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(await response.text());
        const runtimePayload = await response.json();
        setConfig(profileToConfig(nextConfig, runtimePayload));
    };

    const toggleTheme = () => {
        setConfig(prev => ({ ...prev, theme: prev.theme === 'light' ? 'dark' : 'light' }));
    };

    const refreshArtifacts = async () => {
        try {
            const response = await fetch('/api/artifacts');
            if (!response.ok) return;
            const payload = await response.json();
            const artifacts = (payload.artifacts || []).map((artifact: any) => ({
                id: artifact.id,
                type: artifact.artifact_type,
                title: artifact.title,
                createdAt: new Date(artifact.created_at),
                markdown: artifact.markdown,
                payload: artifact.payload,
                downloadJsonUrl: `/api/artifacts/${artifact.id}/download?format=json`,
                downloadMarkdownUrl: `/api/artifacts/${artifact.id}/download?format=markdown`,
                downloadSvgUrl: artifact.artifact_type === 'infographic' ? `/api/artifacts/${artifact.id}/download?format=svg` : undefined
            }));
            setGeneratedContents(artifacts);
        } catch {
            // Generated artifacts are optional for initial rendering.
        }
    };

    const openSlideDeck = (deckId: string | null) => {
        setSlideDeckWorkspaceId(deckId);
        if (deckId) {
            localStorage.setItem('notebooklm-active-slide-deck', deckId);
        } else {
            localStorage.removeItem('notebooklm-active-slide-deck');
        }
    };

    const closeSlideDeck = () => {
        setSlideDeckWorkspaceId(undefined);
        localStorage.removeItem('notebooklm-active-slide-deck');
        refreshArtifacts();
    };

    const rememberSlideDeck = (deckId: string) => {
        setSlideDeckWorkspaceId(deckId);
        localStorage.setItem('notebooklm-active-slide-deck', deckId);
    };

    const handleContentGenerated = (content: GeneratedContent) => {
        setGeneratedContents(prev => [content, ...prev.filter(item => item.id !== content.id)]);
    };

    return (
        <LanguageContext.Provider value={{ lang, setLang }}>
            <div className={`app-container ${config.theme}`}>
                <header className="app-header">
                    <div className="logo-container">
                        <Layers3 className="logo-icon" aria-hidden="true" />
                        <h1 className="logo-title">NotebookLM-Lite</h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="lang-switch">
                            <button onClick={() => setLang('zh')} className={lang === 'zh' ? 'active' : ''}>CN</button>
                            <button onClick={() => setLang('en')} className={lang === 'en' ? 'active' : ''}>EN</button>
                        </div>
                        <button onClick={toggleTheme} className="theme-toggle" title={config.theme === 'light' ? 'Dark' : 'Light'}>
                            {config.theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
                            <span>{lang === 'en' ? (config.theme === 'light' ? 'Dark' : 'Light') : (config.theme === 'light' ? '深色' : '浅色')}</span>
                        </button>
                        <button onClick={() => setShowConfig(true)} className="icon-btn" title="Settings">
                            <Settings size={20} />
                        </button>
                    </div>
                </header>

                {slideDeckWorkspaceId !== undefined ? (
                    <SlideDeckWorkspace
                        deckId={slideDeckWorkspaceId}
                        sourceIds={selectedSourceIds}
                        onBack={closeSlideDeck}
                        onArtifactGenerated={handleContentGenerated}
                        onDeckReady={rememberSlideDeck}
                    />
                ) : (
                    <main className="app-main">
                        <div className="panel panel-left split-panel">
                            <SourcePanel
                                sources={sources}
                                selectedSourceIds={selectedSourceIds}
                                onSourcesChange={setSources}
                                onSelectedSourceIdsChange={setSelectedSourceIds}
                                onRefresh={refreshSources}
                            />
                            <NotesPanel
                                selectedSourceIds={selectedSourceIds}
                                onSourceCreated={refreshSources}
                                refreshKey={notesRefreshKey}
                            />
                        </div>
                        <div className="panel panel-center">
                            <ChatPanel
                                sourceIds={selectedSourceIds}
                                config={config}
                                onSourceCreated={refreshSources}
                                onNoteCreated={() => setNotesRefreshKey(key => key + 1)}
                            />
                        </div>
                        <div className="panel panel-right">
                            <StudioPanel
                                sourceIds={selectedSourceIds}
                                config={config}
                                contents={generatedContents}
                                onContentGenerated={handleContentGenerated}
                                onOpenSlideDeck={openSlideDeck}
                            />
                        </div>
                    </main>
                )}

                {showConfig && (
                    <ConfigModal
                        config={config}
                        onConfigChange={saveRuntimeConfig}
                        onClose={() => setShowConfig(false)}
                    />
                )}
            </div>
        </LanguageContext.Provider>
    );
}

export default App;
