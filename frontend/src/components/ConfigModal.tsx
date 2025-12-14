import React, { useState } from 'react';
import { X, Key, Globe, Cpu, Mic, ChevronDown } from 'lucide-react';
import type { ApiConfig } from '../App';

interface ConfigModalProps {
    config: ApiConfig;
    onConfigChange: (config: ApiConfig) => void;
    onClose: () => void;
}

export const ConfigModal: React.FC<ConfigModalProps> = ({ config, onConfigChange, onClose }) => {
    const [localConfig, setLocalConfig] = useState<ApiConfig>(config);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const handleChange = (key: keyof ApiConfig, value: string) => {
        setLocalConfig(prev => ({ ...prev, [key]: value }));
    };

    const handleSave = () => {
        onConfigChange(localConfig);
        onClose();
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl fade-in">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-light)]">
                    <h2 className="text-lg font-semibold text-[var(--warm-800)]">API 设置</h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-[var(--bg-hover)] rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5 text-[var(--warm-500)]" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
                    {/* Text Model Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center">
                                <Cpu className="w-4 h-4 text-white" />
                            </div>
                            <h3 className="font-medium text-[var(--warm-800)]">文本模型</h3>
                        </div>

                        <div>
                            <label className="label">服务提供商</label>
                            <select
                                value={localConfig.textProvider}
                                onChange={(e) => handleChange('textProvider', e.target.value as 'openai' | 'google')}
                                className="select"
                            >
                                <option value="openai">OpenAI / 兼容接口</option>
                                <option value="google">Google GenAI</option>
                            </select>
                        </div>

                        <div>
                            <label className="label">API Key</label>
                            <div className="relative">
                                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--warm-400)]" />
                                <input
                                    type="password"
                                    value={localConfig.textApiKey}
                                    onChange={(e) => handleChange('textApiKey', e.target.value)}
                                    placeholder="sk-... 或 AIza..."
                                    className="input pl-10"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="label">模型名称</label>
                            <input
                                type="text"
                                value={localConfig.textModel}
                                onChange={(e) => handleChange('textModel', e.target.value)}
                                placeholder={localConfig.textProvider === 'google' ? 'gemini-pro' : 'gpt-4o'}
                                className="input"
                            />
                        </div>

                        {localConfig.textProvider === 'openai' && (
                            <div>
                                <label className="label">Base URL <span className="text-[var(--warm-400)]">(可选)</span></label>
                                <div className="relative">
                                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--warm-400)]" />
                                    <input
                                        type="text"
                                        value={localConfig.textBaseUrl}
                                        onChange={(e) => handleChange('textBaseUrl', e.target.value)}
                                        placeholder="https://api.openai.com/v1"
                                        className="input pl-10"
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="divider" />

                    {/* Speech Model Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center">
                                <Mic className="w-4 h-4 text-white" />
                            </div>
                            <h3 className="font-medium text-[var(--warm-800)]">语音模型</h3>
                        </div>

                        <div>
                            <label className="label">服务提供商</label>
                            <select
                                value={localConfig.speechProvider}
                                onChange={(e) => handleChange('speechProvider', e.target.value as 'openai' | 'dashscope')}
                                className="select"
                            >
                                <option value="openai">OpenAI TTS</option>
                                <option value="dashscope">阿里云 Dashscope (CosyVoice)</option>
                            </select>
                        </div>

                        <div>
                            <label className="label">
                                API Key
                                <span className="text-[var(--warm-400)]">
                                    (留空则使用文本模型 Key)
                                </span>
                            </label>
                            <div className="relative">
                                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--warm-400)]" />
                                <input
                                    type="password"
                                    value={localConfig.speechApiKey}
                                    onChange={(e) => handleChange('speechApiKey', e.target.value)}
                                    placeholder="使用相同的 API Key"
                                    className="input pl-10"
                                />
                            </div>
                        </div>

                        {localConfig.speechProvider === 'openai' && (
                            <div>
                                <label className="label">Base URL <span className="text-[var(--warm-400)]">(可选)</span></label>
                                <div className="relative">
                                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--warm-400)]" />
                                    <input
                                        type="text"
                                        value={localConfig.speechBaseUrl}
                                        onChange={(e) => handleChange('speechBaseUrl', e.target.value)}
                                        placeholder="https://api.openai.com/v1"
                                        className="input pl-10"
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-3 px-6 py-4 border-t border-[var(--border-light)] bg-[var(--warm-50)]">
                    <button onClick={onClose} className="btn btn-secondary">
                        取消
                    </button>
                    <button onClick={handleSave} className="btn btn-primary">
                        保存设置
                    </button>
                </div>
            </div>
        </div>
    );
};
