import React, { useRef, useState } from 'react';
import { Upload, FileText, X, File, Plus, Search, CheckCircle2, Loader2 } from 'lucide-react';
import type { UploadedFile } from '../App';

interface SourcePanelProps {
    files: UploadedFile[];
    onFilesChange: (files: UploadedFile[]) => void;
}

const FILE_ICONS: Record<string, string> = {
    'application/pdf': '📄',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📘',
    'text/plain': '📝',
    'text/markdown': '📑',
    'text/html': '🌐',
};

const ACCEPT_STRING = '.pdf,.docx,.txt,.md,.html,.htm';

export const SourcePanel: React.FC<SourcePanelProps> = ({ files, onFilesChange }) => {
    const [isDragging, setIsDragging] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const getFileIcon = (type: string, name: string) => {
        const ext = name.split('.').pop()?.toLowerCase();
        if (ext === 'pdf') return '📄';
        if (ext === 'docx' || ext === 'doc') return '📘';
        if (ext === 'txt') return '📝';
        if (ext === 'md') return '📑';
        if (ext === 'html' || ext === 'htm') return '🌐';
        return FILE_ICONS[type] || '📄';
    };

    const isSupported = (file: File): boolean => {
        const ext = file.name.split('.').pop()?.toLowerCase();
        return ['pdf', 'docx', 'txt', 'md', 'html', 'htm'].includes(ext || '');
    };

    const uploadFile = async (file: File): Promise<UploadedFile> => {
        const tempId = Math.random().toString(36).substr(2, 9);
        const uploadedFile: UploadedFile = {
            id: tempId,
            name: file.name,
            size: file.size,
            type: file.type,
            status: 'uploading'
        };

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            return { ...uploadedFile, status: 'success', docId: data.id };
        } catch (error) {
            return { ...uploadedFile, status: 'error' };
        }
    };

    const handleFiles = async (fileList: FileList) => {
        const validFiles = Array.from(fileList).filter(isSupported);
        if (validFiles.length === 0) {
            alert('请选择支持的文件格式: PDF, DOCX, TXT, MD, HTML');
            return;
        }

        const placeholders: UploadedFile[] = validFiles.map(f => ({
            id: Math.random().toString(36).substr(2, 9),
            name: f.name,
            size: f.size,
            type: f.type,
            status: 'uploading' as const
        }));

        const newFiles = [...files, ...placeholders];
        onFilesChange(newFiles);

        const results = await Promise.all(validFiles.map(uploadFile));
        const updatedFiles = [...files, ...results];
        onFilesChange(updatedFiles);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files?.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    };

    const removeFile = (id: string) => {
        onFilesChange(files.filter(f => f.id !== id));
    };

    const filteredFiles = files.filter(f =>
        f.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const successCount = files.filter(f => f.status === 'success').length;

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="p-4 border-b border-[var(--border-light)]">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="font-semibold text-[var(--warm-800)]">来源</h2>
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-[var(--primary-600)] hover:bg-[var(--primary-50)] rounded-md transition-colors"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        添加来源
                    </button>
                </div>

                {/* Search */}
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--warm-400)]" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="在网络中搜索新来源"
                        className="input pl-9 text-sm"
                    />
                </div>
            </div>

            {/* Upload Area */}
            <div
                className={`mx-4 mt-4 p-4 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all ${isDragging
                        ? 'border-[var(--primary-400)] bg-[var(--primary-50)]'
                        : 'border-[var(--border-medium)] hover:border-[var(--primary-300)] hover:bg-[var(--warm-50)]'
                    }`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
            >
                <div className="w-10 h-10 mb-2 rounded-full bg-[var(--primary-100)] flex items-center justify-center">
                    <Upload className="w-5 h-5 text-[var(--primary-600)]" />
                </div>
                <p className="text-sm font-medium text-[var(--warm-700)]">拖拽或点击上传</p>
                <p className="text-xs text-[var(--warm-400)] mt-1">PDF, DOCX, TXT, MD, HTML</p>
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={(e) => e.target.files && handleFiles(e.target.files)}
                    accept={ACCEPT_STRING}
                    multiple
                    className="hidden"
                />
            </div>

            {/* File Stats */}
            {files.length > 0 && (
                <div className="mx-4 mt-3 flex items-center gap-2">
                    <span className="text-xs text-[var(--warm-500)]">
                        已选择所有来源
                    </span>
                    <span className="badge badge-success text-xs">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        {successCount} 个文件
                    </span>
                </div>
            )}

            {/* File List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {filteredFiles.map((file) => (
                    <div
                        key={file.id}
                        className={`file-item group ${file.status === 'uploading' ? 'animate-pulse' : ''}`}
                    >
                        <span className="text-xl mr-3">{getFileIcon(file.type, file.name)}</span>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-[var(--warm-800)] truncate">
                                {file.name}
                            </p>
                            <p className="text-xs text-[var(--warm-400)]">
                                {(file.size / 1024).toFixed(1)} KB
                                {file.status === 'uploading' && (
                                    <span className="ml-2 text-[var(--primary-500)]">
                                        <Loader2 className="w-3 h-3 inline animate-spin" /> 上传中...
                                    </span>
                                )}
                                {file.status === 'error' && (
                                    <span className="ml-2 text-[var(--error)]">上传失败</span>
                                )}
                            </p>
                        </div>
                        <button
                            onClick={(e) => { e.stopPropagation(); removeFile(file.id); }}
                            className="p-1 opacity-0 group-hover:opacity-100 hover:bg-[var(--warm-100)] rounded transition-all"
                        >
                            <X className="w-4 h-4 text-[var(--warm-400)]" />
                        </button>
                    </div>
                ))}

                {files.length === 0 && (
                    <div className="text-center py-8 text-[var(--warm-400)]">
                        <FileText className="w-12 h-12 mx-auto mb-2 opacity-30" />
                        <p className="text-sm">暂无来源文件</p>
                        <p className="text-xs mt-1">上传文档开始使用</p>
                    </div>
                )}
            </div>
        </div>
    );
};
