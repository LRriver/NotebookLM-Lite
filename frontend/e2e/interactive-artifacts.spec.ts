import { expect, test } from '@playwright/test';

const source = {
    id: 'src-material',
    kind: 'file',
    title: 'learning.md',
    filename: 'learning.md',
    status: 'ready',
    chunk_count: 3,
    char_count: 280,
    created_at: '2026-06-01T00:00:00Z'
};

const artifactPayloads: Record<string, Record<string, unknown>> = {
    flashcards: {
        title: 'HTTPS 学习卡',
        cards: [
            { front: 'HTTPS 的核心目标是什么？', back: '通过 TLS 提供身份验证、加密和完整性保护。' },
            { front: '证书的作用是什么？', back: '把服务器身份和公钥绑定起来。' }
        ],
        quiz: [
            {
                question: 'HTTPS 使用什么来建立加密连接？',
                options: ['TLS', 'FTP', 'DNS'],
                answer: 'TLS',
                explanation: 'HTTPS 在 HTTP 之下使用 TLS 建立安全通道。'
            }
        ]
    },
    mind_map: {
        title: 'HTTPS 思维图谱',
        root: {
            id: 'root',
            label: 'HTTPS',
            children: [
                { id: 'tls', label: 'TLS 加密', children: [{ id: 'handshake', label: '握手协商', children: [] }] },
                { id: 'cert', label: '证书验证', children: [] }
            ]
        }
    },
    report: {
        title: 'HTTPS 报告',
        summary: 'HTTPS 通过 TLS 保护 HTTP 通信。',
        sections: [
            { heading: '安全属性', body: '包含加密、完整性和身份认证。' },
            { heading: '应用场景', body: '适合登录、支付和 API 通信。' }
        ],
        key_takeaways: ['优先使用 HTTPS', '证书链需要可信']
    },
    faq: {
        title: 'HTTPS FAQ',
        items: [
            { question: 'HTTPS 解决什么问题？', answer: '它通过 TLS 降低窃听、篡改和身份冒充风险。' },
            { question: '证书为什么重要？', answer: '证书把服务器身份和公钥绑定起来。' }
        ]
    },
    data_table: {
        title: '协议对比表',
        columns: ['协议', '安全性', '用途'],
        rows: [
            { 协议: 'HTTP', 安全性: '明文', 用途: '普通网页' },
            { 协议: 'HTTPS', 安全性: 'TLS 加密', 用途: '登录和支付' }
        ]
    },
    infographic: {
        title: 'HTTPS 信息图',
        subtitle: '基于来源生成的视觉摘要',
        sections: [
            { heading: 'TLS 加密', body: '保护 HTTP 内容不被明文读取。', stat: '3 security goals' },
            { heading: '证书验证', body: '确认服务器身份并绑定公钥。', stat: '1 trust chain' }
        ],
        footer: 'Grounded in selected sources.',
        svg: '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="#fff7ed"/><text x="48" y="80">HTTPS 信息图</text><text x="48" y="150">TLS 加密</text></svg>'
    }
};

test('renders NotebookLM-like interactive Studio artifacts', async ({ page }) => {
    let sources: typeof source[] = [];
    let flashcardsInstruction = '';
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources/upload', route => {
        sources = [source];
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(source) });
    });
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources, total: sources.length })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ artifacts: [], total: 0 })
    }));
    await page.route('**/api/artifacts/generate', async route => {
        const body = route.request().postDataJSON() as { artifact_type: string; instruction?: string };
        if (body.artifact_type === 'flashcards') {
            flashcardsInstruction = body.instruction || '';
        }
        const payload = artifactPayloads[body.artifact_type];
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                id: `artifact-${body.artifact_type}`,
                artifact_type: body.artifact_type,
                title: payload.title,
                created_at: '2026-06-01T00:00:00Z',
                markdown: `# ${payload.title}`,
                payload
            })
        });
    });
    await page.route('**/api/slide-decks', async route => {
        if (route.request().method() !== 'POST') return route.fallback();
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                id: 'deck-e2e',
                title: 'Slide Deck',
                source_ids: ['src-material'],
                source_snapshot: [{ source_id: 'src-material', title: 'learning.md', excerpt: 'TLS protects HTTP.' }],
                config_snapshot: { aspect_ratio: '16:9', page_count: 6 },
                outline: null,
                prompt_plan: null,
                slides: [],
                status: 'draft',
                stage: 'created',
                error: null,
                created_at: '2026-06-01T00:00:00Z',
                updated_at: '2026-06-01T00:00:00Z'
            })
        });
    });
    await page.route('**/api/slide-decks/deck-e2e', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            id: 'deck-e2e',
            title: 'Slide Deck',
            source_ids: ['src-material'],
            source_snapshot: [{ source_id: 'src-material', title: 'learning.md', excerpt: 'TLS protects HTTP.' }],
            config_snapshot: { aspect_ratio: '16:9', page_count: 6 },
            outline: null,
            prompt_plan: null,
            slides: [],
            status: 'draft',
            stage: 'created',
            error: null,
            created_at: '2026-06-01T00:00:00Z',
            updated_at: '2026-06-01T00:00:00Z'
        })
    }));

    await page.goto('/');
    await page.locator('input[type="file"]').setInputFiles({
        name: 'learning.md',
        mimeType: 'text/markdown',
        buffer: Buffer.from('# HTTPS\nTLS protects HTTP.')
    });
    await page.getByText('learning.md').click();

    await page.getByRole('button', { name: /卡片/ }).click();
    await page.getByLabel('数量').fill('8');
    await page.getByLabel('难度').selectOption('advanced');
    await page.getByLabel('语言').selectOption('zh');
    await page.getByLabel('自定义要求').fill('优先覆盖 TLS 与证书。');
    await page.getByRole('button', { name: '生成', exact: true }).click();
    expect(flashcardsInstruction).toContain('count: 8');
    expect(flashcardsInstruction).toContain('difficulty: advanced');
    expect(flashcardsInstruction).toContain('language: zh');
    expect(flashcardsInstruction).toContain('优先覆盖 TLS 与证书');
    await page.getByRole('button', { name: /HTTPS 学习卡/ }).click();
    await expect(page.getByText('1 / 2')).toBeVisible();
    await expect(page.getByText('HTTPS 的核心目标是什么？')).toBeVisible();
    await page.getByRole('button', { name: '翻面' }).click();
    await expect(page.getByText('通过 TLS 提供身份验证、加密和完整性保护。')).toBeVisible();
    await page.getByRole('button', { name: 'TLS' }).click();
    await expect(page.getByText('回答正确')).toBeVisible();
    await expect(page.getByText('得分 1 / 1')).toBeVisible();
    await expect(page.getByText('HTTPS 在 HTTP 之下使用 TLS 建立安全通道。')).toBeVisible();
    await page.getByRole('button', { name: '重做' }).click();
    await expect(page.getByText('得分 1 / 1')).not.toBeVisible();

    await page.getByRole('button', { name: /^PPT$/ }).click();
    await expect(page.getByText('Slide Deck 工作区')).toBeVisible();
    await expect(page.getByRole('button', { name: /生成大纲/ })).toBeVisible();
    await page.getByRole('button', { name: /返回/ }).click();

    await page.getByRole('button', { name: /思维图谱/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();
    await expect(page.getByRole('button', { name: 'HTTPS 2' })).toBeVisible();
    await expect(page.getByText('TLS 加密')).toBeVisible();
    await page.getByRole('button', { name: /TLS 加密/ }).click();
    await expect(page.getByText('握手协商')).toBeVisible();

    await page.getByRole('button', { name: /报告/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS 报告/ }).click();
    await expect(page.getByText('HTTPS 通过 TLS 保护 HTTP 通信。')).toBeVisible();
    await expect(page.getByRole('heading', { name: '安全属性' })).toBeVisible();
    await expect(page.getByText('证书链需要可信')).toBeVisible();

    await page.getByRole('button', { name: /^FAQ$/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS FAQ/ }).click();
    await expect(page.getByRole('button', { name: 'HTTPS 解决什么问题？' })).toBeVisible();
    await expect(page.getByText('它通过 TLS 降低窃听、篡改和身份冒充风险。')).not.toBeVisible();
    await page.getByRole('button', { name: 'HTTPS 解决什么问题？' }).click();
    await expect(page.getByText('它通过 TLS 降低窃听、篡改和身份冒充风险。')).toBeVisible();

    await page.getByRole('button', { name: /表格/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /协议对比表/ }).click();
    await expect(page.getByRole('columnheader', { name: '协议' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'TLS 加密' })).toBeVisible();
    const tableRegion = page.getByRole('region', { name: '横向滚动查看完整表格' });
    await expect(tableRegion).toBeVisible();
    await expect.poll(async () => tableRegion.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);

    let developmentMessage = '';
    page.once('dialog', async dialog => {
        developmentMessage = dialog.message();
        await dialog.accept();
    });
    await page.getByRole('button', { name: /视频概览/ }).click();
    expect(developmentMessage).toContain('功能开发中');

    await page.getByRole('button', { name: /信息图/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS 信息图/ }).click();
    await expect(page.getByText('基于来源生成的视觉摘要')).toBeVisible();
    await expect(page.getByText('TLS 加密')).toBeVisible();
    await expect(page.locator('.infographic-frame img')).toBeVisible();
    await expect(page.getByRole('link', { name: /SVG/ })).toBeVisible();
});
