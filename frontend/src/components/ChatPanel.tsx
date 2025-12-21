import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, MoreHorizontal } from 'lucide-react';
import type { ApiConfig } from '../App';
import { useLanguage, translations } from '../App';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    sources?: Array<{ content: string; score: number }>;
}

interface ChatPanelProps {
    documentIds: string[];
    config: ApiConfig;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ documentIds, config }) => {
    const { lang } = useLanguage();
    const t = translations[lang];

    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;
        if (!config.textApiKey) return alert(lang === 'zh' ? '请先配置 API Key' : 'Please configure Text Model API Key settings first.');

        const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input.trim() };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: userMessage.content,
                    document_ids: documentIds,
                    history: messages.map(m => ({ role: m.role, content: m.content })),
                    llm_provider: config.textProvider,
                    llm_api_key: config.textApiKey,
                    llm_base_url: config.textBaseUrl || undefined,
                    llm_model: config.textModel
                })
            });

            if (!response.ok) throw new Error('Request failed');
            const data = await response.json();
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.answer,
                sources: data.sources
            }]);
        } catch {
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: lang === 'zh' ? '抱歉，出了点问题。请检查您的配置。' : 'Sorry, something went wrong. Please check your configuration.'
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <div className="panel-header">
                <h2>{t.chat}</h2>
                <button className="text-xs font-medium text-orange-600 bg-orange-50 px-3 py-1 rounded-full hover:bg-orange-100 transition shadow-sm">
                    {lang === 'zh' ? '新对话' : 'New Chat'}
                </button>
            </div>

            <div className="panel-body flex flex-col">
                <div className="flex-1 overflow-y-auto pb-4 space-y-6 bg-gradient-to-b from-transparent to-[#FFFBF7]">
                    {messages.length === 0 && (
                        <div className="h-full flex flex-col items-center justify-center p-8 text-center">
                            <Sparkles className="w-12 h-12 text-orange-300 mb-3" />
                            <h3 className="text-3xl font-bold text-orange-800/50">{t.startChat}</h3>
                            <p className="text-sm text-gray-400 mt-2 max-w-xs">
                                {lang === 'zh' ? '上传文档以开始分析和提问' : 'Upload documents to start analyzing and asking questions.'}
                            </p>
                        </div>
                    )}

                    {messages.map((message) => (
                        <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] ${message.role === 'user'
                                ? 'bg-gradient-to-br from-[#D97706] to-[#EA580C] text-white px-6 py-4 rounded-2xl rounded-tr-none shadow-lg shadow-orange-500/10'
                                : 'bg-[#F3F4F6] text-slate-800 px-6 py-5 rounded-2xl rounded-tl-none shadow-sm border border-gray-100'}`}>
                                <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</p>
                                {message.sources && message.sources.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-gray-100/20">
                                        <p className="text-[10px] uppercase tracking-wider opacity-70 mb-1">Sources</p>
                                        <div className="flex gap-1 flex-wrap">
                                            {message.sources.slice(0, 2).map((s, i) => (
                                                <span key={i} className="text-[10px] bg-black/5 px-2 py-1 rounded truncate max-w-[150px]">
                                                    {s.content.slice(0, 50)}...
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {isLoading && (
                        <div className="flex justify-start">
                            <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2 shadow-sm">
                                <div className="flex gap-1">
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0s' }} />
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="pt-4 border-t border-gray-100">
                    <div className="relative shadow-lg rounded-full">
                        <input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
                            placeholder={t.inputPlaceholder}
                            className="w-full pl-6 pr-14 py-4 bg-white border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-orange-200 focus:border-orange-300 transition-all placeholder:text-gray-400"
                        />
                        <button
                            onClick={sendMessage}
                            disabled={!input.trim() || isLoading}
                            className={`absolute right-2 top-2 p-2.5 rounded-full transition-all shadow-md flex items-center justify-center ${input.trim()
                                    ? 'bg-orange-600 hover:bg-orange-700 text-white hover:shadow-lg active:scale-95'
                                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                }`}
                        >
                            <Send size={18} className="ml-0.5" />
                        </button>
                    </div>
                    {documentIds.length > 0 && (
                        <div className="text-center mt-2 text-xs text-gray-400">
                            {documentIds.length} {lang === 'zh' ? '个来源已激活' : 'sources active'}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
};
