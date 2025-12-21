import React, { useState } from 'react';
import { X, Key, Cpu, Mic, Globe } from 'lucide-react';
import type { ApiConfig } from '../App';
import { useLanguage } from '../App';

interface ConfigModalProps {
    config: ApiConfig;
    onConfigChange: (config: ApiConfig) => void;
    onClose: () => void;
}

export const ConfigModal: React.FC<ConfigModalProps> = ({ config, onConfigChange, onClose }) => {
    const { lang } = useLanguage();
    const [localConfig, setLocalConfig] = useState<ApiConfig>(config);

    // Translations for ConfigModal
    const t = {
        zh: {
            title: 'API 配置',
            textModel: '文本模型 (LLM)',
            textModelDesc: '用于对话和推理',
            speechModel: '语音模型 (TTS)',
            speechModelDesc: '用于生成播客音频',
            provider: '服务提供商',
            apiKey: 'API Key',
            modelName: '模型名称',
            baseUrl: '接口地址',
            apiKeyOptional: 'API Key (可选)',
            apiKeyPlaceholder: '留空则使用文本API Key',
            cancel: '取消',
            save: '保存',
            googleUrlHint: '留空则使用 Google 官方 API',
            openaiUrlHint: '如使用官方 API 可留空',
            ttsModelPlaceholder: 'tts-1 或 tts-1-hd',
            dashscopeModelPlaceholder: 'cosyvoice-v1'
        },
        en: {
            title: 'API Configuration',
            textModel: 'Text Model (LLM)',
            textModelDesc: 'Handles conversation and reasoning',
            speechModel: 'Speech Model (TTS)',
            speechModelDesc: 'Generates podcast audio',
            provider: 'Provider',
            apiKey: 'API Key',
            modelName: 'Model Name',
            baseUrl: 'Base URL',
            apiKeyOptional: 'API Key (Optional)',
            apiKeyPlaceholder: 'Leave empty to use Text API Key',
            cancel: 'Cancel',
            save: 'Save Changes',
            googleUrlHint: 'Leave empty for official Google API',
            openaiUrlHint: 'Leave empty for official API',
            ttsModelPlaceholder: 'tts-1 or tts-1-hd',
            dashscopeModelPlaceholder: 'cosyvoice-v1'
        }
    }[lang];

    const handleChange = (key: keyof ApiConfig, value: string) => {
        setLocalConfig(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = () => {
        onConfigChange(localConfig);
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-3xl w-full max-w-lg shadow-[0_20px_60px_-15px_rgba(0,0,0,0.3)] animate-fade-in overflow-hidden border border-white/50"
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                    <h2 className="text-xl font-bold text-gray-800">{t.title}</h2>
                    <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded-full transition-colors text-gray-500">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto">
                    {/* Text Model */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600">
                                <Cpu size={20} />
                            </div>
                            <div>
                                <h3 className="font-semibold text-gray-800">{t.textModel}</h3>
                                <p className="text-xs text-gray-500">{t.textModelDesc}</p>
                            </div>
                        </div>

                        <div className="space-y-3 pl-2">
                            <div>
                                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.provider}</label>
                                <select
                                    value={localConfig.textProvider}
                                    onChange={(e) => handleChange('textProvider', e.target.value)}
                                    className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-gray-700 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                >
                                    <option value="openai">OpenAI / Compatible</option>
                                    <option value="google">Google GenAI (Gemini)</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.apiKey}</label>
                                <div className="relative">
                                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                    <input
                                        type="password"
                                        value={localConfig.textApiKey}
                                        onChange={(e) => handleChange('textApiKey', e.target.value)}
                                        placeholder="sk-..."
                                        className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.modelName}</label>
                                    <input
                                        type="text"
                                        value={localConfig.textModel}
                                        onChange={(e) => handleChange('textModel', e.target.value)}
                                        placeholder={localConfig.textProvider === 'google' ? 'gemini-pro' : 'gpt-4o'}
                                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.baseUrl}</label>
                                    <div className="relative">
                                        <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                        <input
                                            type="text"
                                            value={localConfig.textBaseUrl}
                                            onChange={(e) => handleChange('textBaseUrl', e.target.value)}
                                            placeholder={localConfig.textProvider === 'google' ? 'https://generativelanguage.googleapis.com' : 'https://api.openai.com/v1'}
                                            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all text-sm"
                                        />
                                    </div>
                                    <p className="text-[10px] text-gray-400 mt-1">
                                        {localConfig.textProvider === 'google' ? t.googleUrlHint : t.openaiUrlHint}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="h-px bg-gray-100" />

                    {/* Speech Model */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center text-orange-600">
                                <Mic size={20} />
                            </div>
                            <div>
                                <h3 className="font-semibold text-gray-800">{t.speechModel}</h3>
                                <p className="text-xs text-gray-500">{t.speechModelDesc}</p>
                            </div>
                        </div>

                        <div className="space-y-3 pl-2">
                            <div>
                                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.provider}</label>
                                <select
                                    value={localConfig.speechProvider}
                                    onChange={(e) => handleChange('speechProvider', e.target.value)}
                                    className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-gray-700 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                >
                                    <option value="openai">OpenAI TTS</option>
                                    <option value="dashscope">{lang === 'zh' ? '阿里云 Dashscope' : 'Aliyun Dashscope'}</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.apiKeyOptional}</label>
                                <div className="relative">
                                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                    <input
                                        type="password"
                                        value={localConfig.speechApiKey}
                                        onChange={(e) => handleChange('speechApiKey', e.target.value)}
                                        placeholder={t.apiKeyPlaceholder}
                                        className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                    />
                                </div>
                            </div>

                            {/* OpenAI TTS: show Base URL and Model */}
                            {localConfig.speechProvider === 'openai' && (
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.modelName}</label>
                                        <input
                                            type="text"
                                            value={localConfig.speechModel}
                                            onChange={(e) => handleChange('speechModel', e.target.value)}
                                            placeholder={t.ttsModelPlaceholder}
                                            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.baseUrl}</label>
                                        <div className="relative">
                                            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                                            <input
                                                type="text"
                                                value={localConfig.speechBaseUrl}
                                                onChange={(e) => handleChange('speechBaseUrl', e.target.value)}
                                                placeholder="https://api.openai.com/v1"
                                                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all text-sm"
                                            />
                                        </div>
                                        <p className="text-[10px] text-gray-400 mt-1">{t.openaiUrlHint}</p>
                                    </div>
                                </div>
                            )}

                            {/* Dashscope TTS: show only Model */}
                            {localConfig.speechProvider === 'dashscope' && (
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{t.modelName}</label>
                                    <input
                                        type="text"
                                        value={localConfig.speechModel}
                                        onChange={(e) => handleChange('speechModel', e.target.value)}
                                        placeholder={t.dashscopeModelPlaceholder}
                                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:ring-2 focus:ring-amber-500 focus:border-amber-500 outline-none transition-all"
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="p-6 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
                    <button onClick={onClose} className="px-5 py-2.5 rounded-xl border border-gray-200 text-gray-600 font-medium hover:bg-white hover:border-gray-300 transition-all">{t.cancel}</button>
                    <button onClick={handleSave} className="px-5 py-2.5 rounded-xl bg-amber-500 text-white font-medium hover:bg-amber-600 shadow-lg shadow-amber-500/30 transition-all">{t.save}</button>
                </div>
            </div>
        </div>
    );
};
