import React from 'react';

interface MarkdownViewProps {
    content: string;
    className?: string;
}

type TableBlock = {
    headers: string[];
    rows: string[][];
};

const splitTableRow = (line: string) => line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());

const isSeparatorRow = (line: string) => {
    const cells = splitTableRow(line);
    return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell));
};

const renderInline = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        return <React.Fragment key={index}>{part}</React.Fragment>;
    });
};

const renderTable = (table: TableBlock, key: string) => (
    <div key={key} className="markdown-table-wrap">
        <table>
            <thead>
                <tr>
                    {table.headers.map((header, index) => <th key={index}>{renderInline(header)}</th>)}
                </tr>
            </thead>
            <tbody>
                {table.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                        {row.map((cell, cellIndex) => <td key={cellIndex}>{renderInline(cell)}</td>)}
                    </tr>
                ))}
            </tbody>
        </table>
    </div>
);

const unorderedListItem = /^[-*]\s+/;
const orderedListItem = /^\d+[.)]\s+/;

export const MarkdownView: React.FC<MarkdownViewProps> = ({ content, className }) => {
    const lines = content.split(/\r?\n/);
    const elements: React.ReactNode[] = [];
    let index = 0;

    while (index < lines.length) {
        const line = lines[index];
        const trimmed = line.trim();
        if (!trimmed) {
            index += 1;
            continue;
        }

        const heading = /^(#{1,4})\s+(.+)$/.exec(trimmed);
        if (heading) {
            const level = Math.min(heading[1].length, 4);
            const Tag = `h${level}` as keyof JSX.IntrinsicElements;
            elements.push(<Tag key={`h-${index}`}>{renderInline(heading[2])}</Tag>);
            index += 1;
            continue;
        }

        if (unorderedListItem.test(trimmed) || orderedListItem.test(trimmed)) {
            const ordered = orderedListItem.test(trimmed);
            const itemPattern = ordered ? orderedListItem : unorderedListItem;
            const items: string[] = [];
            while (index < lines.length && itemPattern.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(itemPattern, ''));
                index += 1;
            }
            const ListTag = ordered ? 'ol' : 'ul';
            elements.push(
                <ListTag key={`list-${index}`}>
                    {items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item)}</li>)}
                </ListTag>
            );
            continue;
        }

        if (trimmed.includes('|') && index + 1 < lines.length && isSeparatorRow(lines[index + 1])) {
            const headers = splitTableRow(trimmed);
            index += 2;
            const rows: string[][] = [];
            while (index < lines.length && lines[index].trim().includes('|')) {
                rows.push(splitTableRow(lines[index]));
                index += 1;
            }
            elements.push(renderTable({ headers, rows }, `table-${index}`));
            continue;
        }

        const paragraph: string[] = [];
        while (
            index < lines.length &&
            lines[index].trim() &&
            !/^(#{1,4})\s+/.test(lines[index].trim()) &&
            !unorderedListItem.test(lines[index].trim()) &&
            !orderedListItem.test(lines[index].trim()) &&
            !(lines[index].trim().includes('|') && index + 1 < lines.length && isSeparatorRow(lines[index + 1]))
        ) {
            paragraph.push(lines[index].trim());
            index += 1;
        }
        elements.push(<p key={`p-${index}`}>{renderInline(paragraph.join(' '))}</p>);
    }

    return <div className={`markdown-view ${className || ''}`.trim()}>{elements}</div>;
};
