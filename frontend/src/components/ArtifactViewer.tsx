import React, { useEffect, useId, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useLanguage, type GeneratedContent } from '../App';
import { MarkdownView } from './MarkdownView';

type AnyRecord = Record<string, any>;
type MindLayoutNode = {
    id: string;
    label: string;
    childCount: number;
    depth: number;
    x: number;
    y: number;
    width: number;
    height: number;
};

type MindLayoutLink = {
    from: MindLayoutNode;
    to: MindLayoutNode;
};

interface ArtifactViewerProps {
    content: GeneratedContent;
}

const textValue = (value: unknown) => value === undefined || value === null ? '' : String(value);

const mindNodeId = (node: AnyRecord, path: string) => `${path}:${textValue(node.id || node.label || 'node')}`;

const collectExpandableMindIds = (node: AnyRecord, path = 'root'): string[] => {
    const children = Array.isArray(node.children) ? node.children : [];
    const id = mindNodeId(node, path);
    return [
        ...(children.length ? [id] : []),
        ...children.flatMap((child: AnyRecord, index: number) => collectExpandableMindIds(child, `${path}-${index}`))
    ];
};

const mindNodeWidth = (label: string, depth: number) => {
    const base = depth === 0 ? 165 : depth === 1 ? 160 : 130;
    const max = depth === 0 ? 220 : 200;
    return Math.max(base, Math.min(max, label.length * 7 + 46));
};

const layoutMindMap = (root: AnyRecord, expandedIds: Set<string>) => {
    const nodes: MindLayoutNode[] = [];
    const links: MindLayoutLink[] = [];
    let nextLeafY = 28;

    const visit = (node: AnyRecord, depth: number, path: string): MindLayoutNode => {
        const children = Array.isArray(node.children) ? node.children : [];
        const id = mindNodeId(node, path);
        const label = textValue(node.label || node.title || 'Untitled');
        const width = mindNodeWidth(label, depth);
        const height = 42;
        const visibleChildren = expandedIds.has(id)
            ? children.map((child: AnyRecord, index: number) => visit(child, depth + 1, `${path}-${index}`))
            : [];
        const y = visibleChildren.length
            ? visibleChildren.reduce((total, child) => total + child.y, 0) / visibleChildren.length
            : nextLeafY;
        if (!visibleChildren.length) {
            nextLeafY += height + 28;
        }
        const layoutNode = {
            id,
            label,
            childCount: children.length,
            depth,
            x: 28,
            y,
            width,
            height
        };
        nodes.push(layoutNode);
        visibleChildren.forEach(child => links.push({ from: layoutNode, to: child }));
        return layoutNode;
    };

    visit(root, 0, 'root');
    const columnWidths = nodes.reduce<number[]>((widths, node) => {
        widths[node.depth] = Math.max(widths[node.depth] || 0, node.width);
        return widths;
    }, []);
    const columnGap = 18;
    const columnX = columnWidths.reduce<number[]>((positions, width, depth) => {
        positions[depth] = depth === 0 ? 28 : positions[depth - 1] + columnWidths[depth - 1] + columnGap;
        return positions;
    }, []);
    nodes.forEach(node => {
        node.x = columnX[node.depth] || 28;
    });
    const width = Math.max(620, ...nodes.map(node => node.x + node.width + 48));
    const height = Math.max(360, ...nodes.map(node => node.y + node.height + 36));
    return { nodes, links, width, height };
};

const FAQViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const items = Array.isArray(payload.items) ? payload.items : [];
    const [openIndex, setOpenIndex] = useState<number | null>(null);
    const answerIdPrefix = useId();

    if (!items.length) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }

    return (
        <div className="faq-viewer">
            {items.map((item: AnyRecord, index: number) => {
                const expanded = openIndex === index;
                const question = textValue(item?.question);
                const answerId = `${answerIdPrefix}-faq-answer-${index}`;
                return (
                    <div key={`${question}-${index}`} className={`faq-item ${expanded ? 'open' : ''}`}>
                        <button
                            className="faq-question"
                            aria-expanded={expanded}
                            aria-controls={answerId}
                            onClick={() => setOpenIndex(expanded ? null : index)}
                        >
                            <span>{question}</span>
                            <small aria-hidden="true">{index + 1} / {items.length}</small>
                        </button>
                        {expanded && <p id={answerId} className="faq-answer">{textValue(item?.answer)}</p>}
                    </div>
                );
            })}
        </div>
    );
};

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

const MindMapViewer: React.FC<{ payload: AnyRecord; markdown?: string }> = ({ payload, markdown }) => {
    const root = payload.root;
    const expandableIds = useMemo(() => root ? collectExpandableMindIds(root) : [], [root]);
    const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set(expandableIds));
    useEffect(() => {
        setExpandedIds(new Set(expandableIds));
    }, [expandableIds]);
    const layout = useMemo(() => root ? layoutMindMap(root, expandedIds) : null, [root, expandedIds]);
    const toggleNode = (node: MindLayoutNode) => {
        if (!node.childCount) return;
        setExpandedIds(current => {
            const next = new Set(current);
            if (next.has(node.id)) next.delete(node.id);
            else next.add(node.id);
            return next;
        });
    };
    if (!root || !layout) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    const renderNodes = [...layout.nodes].sort((left, right) => left.depth - right.depth || left.y - right.y || left.x - right.x);

    return (
        <div className="mind-map-viewer" role="region" aria-label={textValue(payload.title || 'Mind map')}>
            <div className="mind-map-canvas" style={{ width: layout.width, height: layout.height }}>
                <svg className="mind-map-links" width={layout.width} height={layout.height} aria-hidden="true">
                    {layout.links.map(link => {
                        const x1 = link.from.x + link.from.width;
                        const y1 = link.from.y + link.from.height / 2;
                        const x2 = link.to.x;
                        const y2 = link.to.y + link.to.height / 2;
                        const curve = Math.max(48, (x2 - x1) * 0.55);
                        return (
                            <path
                                key={`${link.from.id}-${link.to.id}`}
                                className={`mind-map-link depth-${Math.min(link.from.depth, 4)}`}
                                d={`M ${x1} ${y1} C ${x1 + curve} ${y1}, ${x2 - curve} ${y2}, ${x2} ${y2}`}
                            />
                        );
                    })}
                </svg>
                {renderNodes.map(node => {
                    const nodeClassName = `mind-graph-node depth-${Math.min(node.depth, 4)} ${node.childCount ? 'has-children' : 'leaf'}`;
                    const nodeStyle = { left: node.x, top: node.y, width: node.width, minHeight: node.height };
                    const nodeContent = (
                        <>
                            <span className="mind-graph-label">{node.label}</span>
                            {node.childCount > 0 && (
                                <span className="mind-graph-count">{expandedIds.has(node.id) ? '−' : '+'}{node.childCount}</span>
                            )}
                        </>
                    );
                    if (!node.childCount) {
                        return (
                            <div key={node.id} className={nodeClassName} style={nodeStyle}>
                                {nodeContent}
                            </div>
                        );
                    }
                    return (
                        <button
                            key={node.id}
                            type="button"
                            className={nodeClassName}
                            style={nodeStyle}
                            onClick={() => toggleNode(node)}
                            aria-label={`${node.label} ${node.childCount}`}
                            aria-expanded={expandedIds.has(node.id)}
                        >
                            {nodeContent}
                        </button>
                    );
                })}
            </div>
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
    const { lang } = useLanguage();
    const title = textValue(payload.title || (lang === 'zh' ? '数据表' : 'Data table'));
    if (!columns.length) {
        return <MarkdownView content={markdown || ''} className="artifact-preview" />;
    }
    return (
        <div className="data-table-viewer data-table-scroll" role="region" aria-label={title} tabIndex={0}>
            <table>
                <caption>{title}</caption>
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
    if (content.type === 'faq') {
        return <FAQViewer payload={payload} markdown={content.markdown} />;
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
