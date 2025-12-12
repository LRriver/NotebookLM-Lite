import React from 'react';

interface DurationSelectorProps {
    value: string;
    onChange: (value: string) => void;
}

const DURATION_OPTIONS = [
    { value: '3-5', label: '3-5 分钟', description: '简短介绍' },
    { value: '5-10', label: '5-10 分钟', description: '标准播客' },
    { value: '10-15', label: '10-15 分钟', description: '深度讨论' },
    { value: '15-20', label: '15-20 分钟', description: '详细探讨' },
];

export const DurationSelector: React.FC<DurationSelectorProps> = ({ value, onChange }) => {
    return (
        <div className="space-y-2">
            <label className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                播客时长
            </label>
            <div className="grid grid-cols-2 gap-2">
                {DURATION_OPTIONS.map((option) => (
                    <button
                        key={option.value}
                        onClick={() => onChange(option.value)}
                        className={`p-3 rounded-lg border text-left transition-all duration-200 ${value === option.value
                                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                                : 'border-slate-700 bg-slate-800/50 text-slate-300 hover:border-slate-600'
                            }`}
                    >
                        <div className="text-sm font-medium">{option.label}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{option.description}</div>
                    </button>
                ))}
            </div>
        </div>
    );
};
