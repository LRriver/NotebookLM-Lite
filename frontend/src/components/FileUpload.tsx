import React, { useRef, useState } from 'react';
import { Upload, FileText, X, File, FileSpreadsheet } from 'lucide-react';

interface UploadedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    status: 'uploading' | 'success' | 'error';
    docId?: string;
}

interface FileUploadProps {
    onFilesChange: (files: UploadedFile[]) => void;
    multiple?: boolean;
}

// 支持的文件类型
const SUPPORTED_TYPES = {
    'application/pdf': { icon: FileText, color: 'text-red-400', label: 'PDF' },
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': { icon: FileSpreadsheet, color: 'text-blue-400', label: 'DOCX' },
    'text/plain': { icon: File, color: 'text-gray-400', label: 'TXT' },
    'text/markdown': { icon: File, color: 'text-purple-400', label: 'MD' },
    'text/html': { icon: File, color: 'text-orange-400', label: 'HTML' },
};

const ACCEPT_STRING = '.pdf,.docx,.txt,.md,.html,.htm';

export const FileUpload: React.FC<FileUploadProps> = ({ onFilesChange, multiple = true }) => {
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const getFileIcon = (type: string) => {
        const config = SUPPORTED_TYPES[type as keyof typeof SUPPORTED_TYPES];
        if (config) {
            const Icon = config.icon;
            return <Icon className={`w-5 h-5 ${config.color}`} />;
        }
        return <File className="w-5 h-5 text-gray-400" />;
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

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            const data = await response.json();
            return {
                ...uploadedFile,
                status: 'success',
                docId: data.id
            };
        } catch (error) {
            return {
                ...uploadedFile,
                status: 'error'
            };
        }
    };

    const handleFiles = async (fileList: FileList) => {
        const validFiles = Array.from(fileList).filter(isSupported);

        if (validFiles.length === 0) {
            alert('请选择支持的文件格式: PDF, DOCX, TXT, MD, HTML');
            return;
        }

        // 添加占位文件（显示上传中状态）
        const placeholders: UploadedFile[] = validFiles.map(f => ({
            id: Math.random().toString(36).substr(2, 9),
            name: f.name,
            size: f.size,
            type: f.type,
            status: 'uploading' as const
        }));

        const newFiles = multiple ? [...files, ...placeholders] : placeholders;
        setFiles(newFiles);
        onFilesChange(newFiles);

        // 上传文件
        const results = await Promise.all(validFiles.map(uploadFile));

        // 更新状态
        const updatedFiles = multiple
            ? [...files, ...results]
            : results;

        setFiles(updatedFiles);
        onFilesChange(updatedFiles);
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    };

    const removeFile = (id: string) => {
        const newFiles = files.filter(f => f.id !== id);
        setFiles(newFiles);
        onFilesChange(newFiles);
    };

    return (
        <div className="w-full h-full flex flex-col">
            <div className="flex items-center mb-4">
                <div className="w-8 h-8 rounded bg-purple-500/20 flex items-center justify-center mr-3 text-purple-400">
                    📄
                </div>
                <h2 className="text-sm font-bold text-purple-400 tracking-widest uppercase">知识库</h2>
            </div>

            {/* 上传区域 */}
            <div
                className={`group relative border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-6 cursor-pointer transition-all duration-300 ${isDragging
                        ? 'border-cyan-400 bg-cyan-900/20'
                        : 'border-slate-600 hover:border-cyan-500 hover:bg-cyan-900/10'
                    }`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
            >
                <div className="w-12 h-12 mb-3 rounded-full bg-slate-800 flex items-center justify-center group-hover:scale-110 transition-transform border border-slate-600 group-hover:border-cyan-500">
                    <Upload className="w-6 h-6 text-slate-400 group-hover:text-cyan-400 transition-colors" />
                </div>
                <p className="text-sm text-slate-200 font-bold mb-1">拖拽或点击上传</p>
                <p className="text-xs text-slate-500">支持 PDF, DOCX, TXT, MD, HTML</p>
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept={ACCEPT_STRING}
                    multiple={multiple}
                    className="hidden"
                />
            </div>

            {/* 已上传文件列表 */}
            {files.length > 0 && (
                <div className="mt-4 space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                    {files.map((file) => (
                        <div
                            key={file.id}
                            className={`flex items-center justify-between p-3 rounded-lg border ${file.status === 'uploading'
                                    ? 'bg-slate-800/50 border-slate-700 animate-pulse'
                                    : file.status === 'success'
                                        ? 'bg-slate-800/50 border-green-500/30'
                                        : 'bg-red-900/20 border-red-500/30'
                                }`}
                        >
                            <div className="flex items-center overflow-hidden">
                                {getFileIcon(file.type)}
                                <div className="ml-3 min-w-0">
                                    <p className="text-sm text-slate-200 truncate">{file.name}</p>
                                    <p className="text-xs text-slate-500">
                                        {(file.size / 1024).toFixed(1)} KB
                                        {file.status === 'uploading' && ' · 上传中...'}
                                        {file.status === 'error' && ' · 上传失败'}
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={(e) => { e.stopPropagation(); removeFile(file.id); }}
                                className="p-1.5 hover:bg-red-500/20 rounded text-slate-500 hover:text-red-400 transition-colors ml-2 flex-shrink-0"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
