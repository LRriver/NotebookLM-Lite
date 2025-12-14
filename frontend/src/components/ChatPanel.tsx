import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, Loader2, MoreHorizontal, Sparkles } from 'lucide-react';
import type { ApiConfig } from '../App';

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
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
        }
    }, [input]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;
        if (!config.textApiKey) {
            alert('请先在设置中配置文本模型 API Key');
            return;
        }

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim()
        };

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

            if (!response.ok) throw new Error('请求失败');

            const data = await response.json();
            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.answer,
                sources: data.sources
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: '抱歉，处理请求时出现错误。请检查配置并重试。'
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-light)] bg-white">
                <div className="flex items-center gap-2">
                    <h2 className="font-semibold text-[var(--warm-800)]">对话</h2>
                    <span className="text-xs text-[var(--warm-400)]">
                        {documentIds.length > 0 ? `基于 ${documentIds.length} 个文档` : '上传文档开始对话'}
                    </span>
                </div>
                <button className="p-2 hover:bg-[var(--bg-hover)] rounded-lg transition-colors">
                    <MoreHorizontal className="w-5 h-5 text-[var(--warm-400)]" />
                </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <div className="w-16 h-16 mb-4 rounded-2xl bg-gradient-to-br from-amber-100 to-orange-100 flex items-center justify-center">
                            <Sparkles className="w-8 h-8 text-[var(--primary-500)]" />
                        </div>
                        <h3 className="text-lg font-semibold text-[var(--warm-700)] mb-2">
                            开始对话
                        </h3>
                        <p className="text-sm text-[var(--warm-400)] max-w-md">
                            上传文档后，可以基于文档内容进行问答。支持多轮对话和上下文理解。
                        </p>
                    </div>
                )}

                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div className={`flex max-w-[75%] ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${message.role === 'user'
                                    ? 'bg-gradient-to-br from-amber-400 to-orange-500 ml-3'
                                    : 'bg-[var(--warm-100)] mr-3'
                                }`}>
                                {message.role === 'user'
                                    ? <User className="w-4 h-4 text-white" />
                                    : <Bot className="w-4 h-4 text-[var(--warm-600)]" />
                                }
                            </div>
                            <div className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}>
                                <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                                {message.sources && message.sources.length > 0 && (
                                    <div className="mt-3 pt-3 border-t border-[var(--border-light)]">
                                        <p className="text-xs text-[var(--warm-500)] mb-2">📚 参考来源:</p>
                                        {message.sources.slice(0, 2).map((source, idx) => (
                                            <p key={idx} className="text-xs text-[var(--warm-500)] bg-[var(--warm-50)] p-2 rounded mt-1 line-clamp-2">
                                                {source.content}
                                            </p>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex justify-start">
                        <div className="flex items-center bg-white border border-[var(--border-light)] rounded-2xl px-4 py-3">
                            <Loader2 className="w-4 h-4 animate-spin text-[var(--primary-500)]" />
                            <span className="ml-2 text-sm text-[var(--warm-500)]">思考中...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-[var(--border-light)] bg-white">
                <div className="flex items-end gap-3 max-w-4xl mx-auto">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="开始输入..."
                            rows={1}
                            className="input resize-none pr-12"
                            style={{ minHeight: '44px' }}
                        />
                        <span className="absolute right-3 bottom-3 text-xs text-[var(--warm-400)]">
                            {documentIds.length} 个来源
                        </span>
                    </div>
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading}
                        className={`flex items-center justify-center w-11 h-11 rounded-xl transition-all ${input.trim() && !isLoading
                                ? 'bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg shadow-orange-200 hover:shadow-xl hover:shadow-orange-300'
                                : 'bg-[var(--warm-100)] text-[var(--warm-400)] cursor-not-allowed'
                            }`}
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
};
