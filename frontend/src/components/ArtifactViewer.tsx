import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { GeneratedContent } from '../App';
import { MarkdownView } from './MarkdownView';

type AnyRecord = Record<string, any>;

interface ArtifactViewerProps {
    content: GeneratedContent;
}

const textValue = (value: unknown) => value === undefined || value === null ? '' : String(value);

const FlashcardsViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const cards = Array.isArray(payload.cards) ? payload.cards : [];
    const quiz = Array.isArray(payload.quiz) ? payload.quiz : [];
    const [cardIndex, setCardIndex] = useState(0);
    const [flipped, setFlipped] = useState(false);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const current = cards[cardIndex] || {};

    if (!cards.length && !quiz.length) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }

    const move = (delta: number) => {
        setCardIndex(index => Math.min(cards.length - 1, Math.max(0, index + delta)));
        setFlipped(false);
    };
    const answeredCount = Object.keys(answers).length;
    const score = quiz.reduce((total, item, index) => total + (answers[index] === item.answer ? 1 : 0), 0);
    const resetQuiz = () => setAnswers({});

    return (
        <div className="artifact-interactive">
            {cards.length > 0 && (
                <>
                    <div className={`flashcard ${flipped ? 'flipped' : ''}`}>
                        <div className="flashcard-meta">{cardIndex + 1} / {cards.length}</div>
                        <div className="flashcard-label">{flipped ? 'Back' : 'Front'}</div>
                        <p>{textValue(flipped ? current.back : current.front)}</p>
                    </div>
                    <div className="artifact-controls">
                        <button className="secondary-btn compact" onClick={() => move(-1)} disabled={cardIndex === 0}>
                            <ChevronLeft size={15} /> 上一张
                        </button>
                        <button className="primary-btn compact" onClick={() => setFlipped(value => !value)}>翻面</button>
                        <button className="secondary-btn compact" onClick={() => move(1)} disabled={cardIndex === cards.length - 1}>
                            下一张 <ChevronRight size={15} />
                        </button>
                    </div>
                </>
            )}

            {quiz.length > 0 && (
                <div className="quiz-panel">
                    <div className="quiz-head">
                        <h4>Quiz</h4>
                        {answeredCount === quiz.length && (
                            <div className="quiz-score">
                                得分 {score} / {quiz.length}
                                <button className="secondary-btn compact" onClick={resetQuiz}>重做</button>
                            </div>
                        )}
                    </div>
                    {quiz.map((item, index) => {
                        const selected = answers[index];
                        const options = Array.isArray(item.options) ? item.options : [];
                        const correct = selected && selected === item.answer;
                        return (
                            <div key={index} className="quiz-item">
                                <div className="quiz-question">{textValue(item.question)}</div>
                                <div className="quiz-options">
                                    {options.map((option: unknown) => {
                                        const optionText = textValue(option);
                                        const active = selected === optionText;
                                        return (
                                            <button
                                                key={optionText}
                                                className={`quiz-option ${active ? 'selected' : ''}`}
                                                onClick={() => setAnswers(prev => ({ ...prev, [index]: optionText }))}
                                            >
                                                {optionText}
                                            </button>
                                        );
                                    })}
                                </div>
                                {selected && (
                                    <div className={`quiz-feedback ${correct ? 'correct' : 'wrong'}`}>
                                        {correct ? '回答正确' : `正确答案：${textValue(item.answer)}`}
                                        {item.explanation && <p>{textValue(item.explanation)}</p>}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

const InfographicViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const svg = textValue(payload.svg);
    const [imageUrl, setImageUrl] = useState('');
    useEffect(() => {
        if (!svg.trim()) {
            setImageUrl('');
            return;
        }
        if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
            const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
            setImageUrl(url);
            return () => URL.revokeObjectURL?.(url);
        }
        setImageUrl(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
    }, [svg]);

    if (!svg.trim()) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    return (
        <div className="infographic-viewer">
            {payload.subtitle && <p className="infographic-subtitle">{textValue(payload.subtitle)}</p>}
            <div className="infographic-frame">
                {imageUrl && <img src={imageUrl} alt={textValue(payload.title || 'Infographic')} />}
            </div>
            {Array.isArray(payload.sections) && payload.sections.length > 0 && (
                <div className="infographic-sections">
                    {payload.sections.map((section: AnyRecord, index: number) => (
                        <div key={`${textValue(section.heading)}-${index}`} className="infographic-section-item">
                            <strong>{textValue(section.heading)}</strong>
                            {section.stat && <span>{textValue(section.stat)}</span>}
                            <p>{textValue(section.body)}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const MindMapNode: React.FC<{ node: AnyRecord; depth?: number }> = ({ node, depth = 0 }) => {
    const children = Array.isArray(node.children) ? node.children : [];
    const [expanded, setExpanded] = useState(depth === 0);
    return (
        <div className="mind-node" style={{ ['--depth' as string]: depth }}>
            <button className="mind-node-button" onClick={() => setExpanded(value => !value)}>
                <span className="mind-node-dot" />
                <span>{textValue(node.label)}</span>
                {children.length > 0 && <span className="mind-node-count">{children.length}</span>}
            </button>
            {expanded && children.length > 0 && (
                <div className="mind-node-children">
                    {children.map((child: AnyRecord, index: number) => <MindMapNode key={child.id || index} node={child} depth={depth + 1} />)}
                </div>
            )}
        </div>
    );
};

const MindMapViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    if (!payload.root) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    return (
        <div className="mind-map-viewer">
            <MindMapNode node={payload.root} />
        </div>
    );
};

const ReportViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const sections = Array.isArray(payload.sections) ? payload.sections : [];
    const takeaways = Array.isArray(payload.key_takeaways) ? payload.key_takeaways : [];
    if (!payload.summary && !sections.length) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    return (
        <div className="report-viewer">
            {payload.summary && <p className="report-summary">{textValue(payload.summary)}</p>}
            {sections.map((section, index) => (
                <section key={index} className="report-section">
                    <h3>{textValue(section.heading)}</h3>
                    <p>{textValue(section.body)}</p>
                </section>
            ))}
            {takeaways.length > 0 && (
                <div className="takeaway-panel">
                    <h4>Key Takeaways</h4>
                    <ul>
                        {takeaways.map((item, index) => <li key={index}>{textValue(item)}</li>)}
                    </ul>
                </div>
            )}
        </div>
    );
};

const DataTableViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const columns = Array.isArray(payload.columns) ? payload.columns : [];
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!columns.length) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    return (
        <div className="data-table-viewer">
            <table>
                <thead>
                    <tr>
                        {columns.map((column: unknown) => <th key={textValue(column)}>{textValue(column)}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row: AnyRecord, rowIndex: number) => (
                        <tr key={rowIndex}>
                            {columns.map((column: unknown) => {
                                const key = textValue(column);
                                return <td key={key}>{textValue(row[key])}</td>;
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ content }) => {
    const payload = useMemo(() => content.payload || {}, [content.payload]);
    if (payload.adapter_status === 'placeholder') {
        return (
            <div className="placeholder-artifact">
                <div className="placeholder-label">{textValue(payload.official_capability || content.type)}</div>
                <p>{textValue(payload.message || content.markdown)}</p>
            </div>
        );
    }
    if (content.type === 'flashcards' || content.type === 'quiz') {
        return <FlashcardsViewer payload={payload} markdown={content.markdown} />;
    }
    if (content.type === 'mind_map') {
        return <MindMapViewer payload={payload} markdown={content.markdown} />;
    }
    if (content.type === 'report' || content.type === 'study_guide') {
        return <ReportViewer payload={payload} markdown={content.markdown} />;
    }
    if (content.type === 'data_table') {
        return <DataTableViewer payload={payload} markdown={content.markdown} />;
    }
    if (content.type === 'infographic') {
        return <InfographicViewer payload={payload} markdown={content.markdown} />;
    }
    return <MarkdownView content={content.markdown || content.transcript || JSON.stringify(payload, null, 2)} className="artifact-preview" />;
};
