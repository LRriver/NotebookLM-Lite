import React, { useState, createContext, useContext } from 'react';
import { SourcePanel } from './components/SourcePanel';
import { ChatPanel } from './components/ChatPanel';
import { StudioPanel } from './components/StudioPanel';
import { ConfigModal } from './components/ConfigModal';
import { Settings } from 'lucide-react';

// Language Context
export type Language = 'zh' | 'en';
export const LanguageContext = createContext<{ lang: Language; setLang: (l: Language) => void }>({
    lang: 'zh',
    setLang: () => { }
});
export const useLanguage = () => useContext(LanguageContext);

// Translations
export const translations = {
    zh: {
        sources: '来源',
        chat: '对话',
        studio: '工作室',
        generatedContent: '已生成内容',
        searchPlaceholder: '搜索来源...',
        dragDropText: '将文件拖放到此处，或点击选择',
        addSource: '添加来源',
        startChat: '开始对话',
        inputPlaceholder: '询问有关您的文档的问题...',
        noContent: '暂无生成内容',
        tools: {
            podcast: '播客',
            mindmap: '思维导图',
            ppt: '演示文稿',
            faq: '常见问题'
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
        generatedContent: 'Generated Content',
        searchPlaceholder: 'Search sources...',
        dragDropText: 'Drag and drop files here, or click to select',
        addSource: 'Add Source',
        startChat: 'Start Chat',
        inputPlaceholder: 'Ask a question about your documents...',
        noContent: 'No content generated yet',
        tools: {
            podcast: 'Podcast',
            mindmap: 'Mind Map',
            ppt: 'PPT',
            faq: 'FAQ'
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
    textProvider: 'openai' | 'google';
    textApiKey: string;
    textBaseUrl: string;
    textModel: string;
    speechProvider: 'openai' | 'dashscope';
    speechApiKey: string;
    speechBaseUrl: string;
    speechModel: string;
}

export interface UploadedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    status: 'uploading' | 'success' | 'error';
    docId?: string;
}

export interface GeneratedContent {
    id: string;
    type: 'podcast' | 'ppt' | 'mindmap';
    title: string;
    createdAt: Date;
    audioUrl?: string;
    transcript?: string;
}

function App() {
    const [lang, setLang] = useState<Language>('zh');
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [generatedContents, setGeneratedContents] = useState<GeneratedContent[]>([]);
    const [showConfig, setShowConfig] = useState(false);
    const [config, setConfig] = useState<ApiConfig>({
        textProvider: 'openai',
        textApiKey: '',
        textBaseUrl: '',
        textModel: '',
        speechProvider: 'openai',
        speechApiKey: '',
        speechBaseUrl: '',
        speechModel: ''
    });

    const t = translations[lang];

    const documentIds = files
        .filter(f => f.status === 'success' && f.docId)
        .map(f => f.docId!);

    const handlePodcastGenerated = (content: GeneratedContent) => {
        setGeneratedContents(prev => [content, ...prev]);
    };

    return (
        <LanguageContext.Provider value={{ lang, setLang }}>
            <div className="app-container">
                {/* Header */}
                <header className="app-header">
                    <div className="logo-container">
                        {/* SVG Logo - Three Stacked Layers */}
                        <div className="w-9 h-9 flex items-center justify-center">
                            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full text-orange-600">
                                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-orange-700 to-orange-500">
                            NotebookLM Lite
                        </h1>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Language Switcher */}
                        <div className="flex items-center bg-white/60 backdrop-blur-sm rounded-full p-1 border border-orange-100 shadow-sm">
                            <button
                                onClick={() => setLang('zh')}
                                className={`px-3 py-1 text-xs font-bold rounded-full transition-all ${lang === 'zh' ? 'bg-orange-500 text-white shadow-md' : 'text-gray-500 hover:bg-orange-50'}`}
                            >
                                CN
                            </button>
                            <button
                                onClick={() => setLang('en')}
                                className={`px-3 py-1 text-xs font-bold rounded-full transition-all ${lang === 'en' ? 'bg-orange-500 text-white shadow-md' : 'text-gray-500 hover:bg-orange-50'}`}
                            >
                                EN
                            </button>
                        </div>

                        <button
                            onClick={() => setShowConfig(true)}
                            className="p-2 hover:bg-orange-100 rounded-full transition-colors text-gray-600"
                        >
                            <Settings size={20} />
                        </button>
                    </div>
                </header>

                {/* Main Content */}
                <main className="app-main">
                    {/* Left Panel - Sources */}
                    <div className="panel panel-left">
                        <SourcePanel
                            files={files}
                            onFilesChange={setFiles}
                        />
                    </div>

                    {/* Center Panel - Chat */}
                    <div className="panel panel-center">
                        <ChatPanel
                            documentIds={documentIds}
                            config={config}
                        />
                    </div>

                    {/* Right Panel - Studio */}
                    <div className="panel panel-right">
                        <StudioPanel
                            documentIds={documentIds}
                            config={config}
                            contents={generatedContents}
                            onContentGenerated={handlePodcastGenerated}
                        />
                    </div>
                </main>

                {/* Config Modal */}
                {showConfig && (
                    <ConfigModal
                        config={config}
                        onConfigChange={setConfig}
                        onClose={() => setShowConfig(false)}
                    />
                )}
            </div>
        </LanguageContext.Provider>
    );
}

export default App;
