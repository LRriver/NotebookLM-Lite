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
        columns: ['协议', '安全性', '用途', '证书配置', '兼容性', '运维关注', '典型配置与注意事项'],
        rows: [
            {
                协议: 'HTTP',
                安全性: '明文',
                用途: '普通网页',
                证书配置: '不需要证书',
                兼容性: '所有浏览器支持',
                运维关注: '避免承载敏感业务',
                典型配置与注意事项: '只适合公开内容，不应用于登录、支付、私密 API 或需要完整性保护的业务链路。'
            },
            {
                协议: 'HTTPS',
                安全性: 'TLS 加密',
                用途: '登录和支付',
                证书配置: '需要可信证书链',
                兼容性: '现代浏览器默认优先',
                运维关注: '续期、TLS 策略、混合内容',
                典型配置与注意事项: '需要可信证书链、现代 TLS 配置、证书续期监控，并避免混合内容。'
            }
        ]
    },
    video_overview: {
        title: '视频概览占位',
        adapter_status: 'placeholder',
        official_capability: 'Video Overview',
        message: '功能开发中，后续会接入视频概览生成。'
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

const luminance = (cssColor: string) => {
    const colors = [...cssColor.matchAll(/rgba?\((\d+),\s*(\d+),\s*(\d+)/g)];
    if (!colors.length) return 255;
    return Math.max(...colors.map(([, red, green, blue]) => 0.2126 * Number(red) + 0.7152 * Number(green) + 0.0722 * Number(blue)));
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
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /^PPT$/ }).click();
    await expect(page.getByText('Slide Deck 工作区')).toBeVisible();
    await expect(page.getByRole('button', { name: /生成大纲/ })).toBeVisible();
    await page.getByRole('button', { name: /返回/ }).click();

    await page.getByRole('button', { name: /思维图谱/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();
    await expect.poll(async () => page.locator('.panel-right').evaluate(element => Math.round(element.getBoundingClientRect().width))).toBeGreaterThan(500);
    await expect(page.getByRole('button', { name: 'HTTPS 2' })).toBeVisible();
    await expect(page.getByText('TLS 加密')).toBeVisible();
    await expect(page.getByText('握手协商')).toBeVisible();
    await expect(page.locator('.mind-map-viewer button').first()).toHaveAccessibleName('HTTPS 2');
    await expect(page.locator('.mind-map-viewer')).not.toHaveAttribute('tabindex', '0');
    const rootBox = await page.getByRole('button', { name: 'HTTPS 2' }).boundingBox();
    const childBox = await page.getByRole('button', { name: /TLS 加密/ }).boundingBox();
    expect(rootBox).not.toBeNull();
    expect(childBox).not.toBeNull();
    expect(childBox!.x).toBeGreaterThan(rootBox!.x + rootBox!.width);
    await expect.poll(async () => page.locator('.mind-map-link').count()).toBeGreaterThanOrEqual(2);
    await expect.poll(async () => page.locator('.mind-map-link').first().evaluate(element => {
        const style = window.getComputedStyle(element);
        return {
            stroke: style.stroke,
            strokeWidth: Number.parseFloat(style.strokeWidth),
            opacity: Number.parseFloat(style.opacity || '1')
        };
    })).toMatchObject({ strokeWidth: expect.any(Number), opacity: expect.any(Number) });
    const firstLinkStyle = await page.locator('.mind-map-link').first().evaluate(element => {
        const style = window.getComputedStyle(element);
        return {
            stroke: style.stroke,
            strokeWidth: Number.parseFloat(style.strokeWidth),
            opacity: Number.parseFloat(style.opacity || '1')
        };
    });
    expect(firstLinkStyle.stroke).not.toBe('none');
    expect(firstLinkStyle.strokeWidth).toBeGreaterThanOrEqual(2);
    expect(firstLinkStyle.opacity).toBeGreaterThanOrEqual(0.8);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /报告/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS 报告/ }).click();
    await expect(page.getByText('HTTPS 通过 TLS 保护 HTTP 通信。')).toBeVisible();
    await expect(page.getByRole('heading', { name: '安全属性' })).toBeVisible();
    await expect(page.getByText('证书链需要可信')).toBeVisible();
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /^FAQ$/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /HTTPS FAQ/ }).click();
    await expect(page.getByRole('button', { name: 'HTTPS 解决什么问题？' })).toBeVisible();
    await expect(page.getByText('它通过 TLS 降低窃听、篡改和身份冒充风险。')).not.toBeVisible();
    await page.getByRole('button', { name: 'HTTPS 解决什么问题？' }).click();
    await expect(page.getByText('它通过 TLS 降低窃听、篡改和身份冒充风险。')).toBeVisible();
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /表格/ }).click();
    await page.getByRole('button', { name: '生成', exact: true }).click();
    await page.getByRole('button', { name: /协议对比表/ }).click();
    await expect(page.getByRole('columnheader', { name: '协议' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'TLS 加密' })).toBeVisible();
    const tableRegion = page.getByRole('region', { name: '协议对比表' });
    await expect(tableRegion).toBeVisible();
    await expect.poll(async () => tableRegion.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
    await tableRegion.evaluate(element => { element.scrollLeft = element.scrollWidth; });
    await expect.poll(async () => tableRegion.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
    const regionBox = await tableRegion.boundingBox();
    const lastCellBox = await page.getByRole('cell', { name: /需要可信证书链、现代 TLS 配置/ }).boundingBox();
    expect(regionBox).not.toBeNull();
    expect(lastCellBox).not.toBeNull();
    expect(lastCellBox!.x + lastCellBox!.width).toBeLessThanOrEqual(regionBox!.x + regionBox!.width + 1);
    await page.getByRole('button', { name: /工作室/ }).click();

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

test('keeps artifact detail full-width in narrow stacked layouts', async ({ page }) => {
    await page.setViewportSize({ width: 760, height: 900 });
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: [{
                id: 'artifact-mind_map',
                artifact_type: 'mind_map',
                title: artifactPayloads.mind_map.title,
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: '# HTTPS 思维图谱',
                payload: artifactPayloads.mind_map
            }],
            total: 1
        })
    }));

    await page.goto('/');
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();

    await expect.poll(async () => page.locator('.panel-right').evaluate(element => Math.round(element.getBoundingClientRect().width))).toBeGreaterThan(680);
});

test('preserves usable chat width when artifact details are open on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 860 });
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: [{
                id: 'artifact-mind_map',
                artifact_type: 'mind_map',
                title: artifactPayloads.mind_map.title,
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: '# HTTPS 思维图谱',
                payload: artifactPayloads.mind_map
            }],
            total: 1
        })
    }));

    await page.goto('/');
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();

    await expect.poll(async () => page.locator('.panel-center').evaluate(element => Math.round(element.getBoundingClientRect().width))).toBeGreaterThan(300);
});

test('keeps artifact detail layout usable on phone widths', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 860 });
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: [{
                id: 'artifact-mind_map',
                artifact_type: 'mind_map',
                title: artifactPayloads.mind_map.title,
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: '# HTTPS 思维图谱',
                payload: artifactPayloads.mind_map
            }],
            total: 1
        })
    }));

    await page.goto('/');
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();

    await expect.poll(async () => page.locator('.panel-center').evaluate(element => Math.round(element.getBoundingClientRect().width))).toBeGreaterThan(300);
    await expect.poll(async () => page.locator('.panel-right').evaluate(element => Math.round(element.getBoundingClientRect().width))).toBeGreaterThan(300);
});

test('opens persisted slide deck artifacts in the Slide Deck workspace', async ({ page }) => {
    let requestedDeckId = '';
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: [{
                id: 'artifact-slide-deck',
                artifact_type: 'slide_deck',
                title: '恢复的演示文稿',
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: '# 恢复的演示文稿',
                payload: { deck_id: 'deck-restored-1' }
            }],
            total: 1
        })
    }));
    await page.route('**/api/slide-decks/deck-restored-1', route => {
        requestedDeckId = 'deck-restored-1';
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                id: 'deck-restored-1',
                title: '恢复的演示文稿',
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

    await page.goto('/');
    await page.getByRole('button', { name: /恢复的演示文稿/ }).click();

    await expect(page.getByText('Slide Deck 工作区')).toBeVisible();
    await expect(page.getByText('恢复的演示文稿')).toBeVisible();
    await expect(page.getByRole('button', { name: /生成大纲/ })).toBeVisible();
    expect(requestedDeckId).toBe('deck-restored-1');

    await page.getByRole('button', { name: /返回/ }).click();
    await expect(page.getByRole('button', { name: /恢复的演示文稿/ })).toBeVisible();
});

test('keeps Studio artifact details readable and visually integrated in dark mode', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('notebooklm-theme', 'dark'));
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: [{
                id: 'artifact-mind_map',
                artifact_type: 'mind_map',
                title: artifactPayloads.mind_map.title,
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: '# HTTPS 思维图谱',
                payload: artifactPayloads.mind_map
            }],
            total: 1
        })
    }));

    await page.goto('/');
    await page.getByRole('button', { name: /HTTPS 思维图谱/ }).click();

    const styles = await page.evaluate(() => {
        const styleOf = (selector: string) => window.getComputedStyle(document.querySelector(selector)!);
        return {
            backColor: styleOf('.studio-back-btn').color,
            titleColor: styleOf('.artifact-detail-name').color,
            mindMapBackground: styleOf('.mind-map-viewer').backgroundImage,
            mindNodeBackground: styleOf('.mind-graph-node').backgroundColor
        };
    });

    expect(luminance(styles.backColor)).toBeGreaterThan(170);
    expect(luminance(styles.titleColor)).toBeGreaterThan(170);
    expect(luminance(styles.mindMapBackground)).toBeLessThan(120);
    expect(luminance(styles.mindNodeBackground)).toBeLessThan(160);
});

test('keeps non-mind-map Studio artifact detail surfaces integrated in dark mode', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('notebooklm-theme', 'dark'));
    await page.route('**/api/config', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ models: {} })
    }));
    await page.route('**/api/sources', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: [source], total: 1 })
    }));
    await page.route('**/api/notes', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notes: [], total: 0 })
    }));
    await page.route('**/api/artifacts', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            artifacts: ['flashcards', 'report', 'faq', 'data_table', 'infographic', 'video_overview'].map(type => ({
                id: `artifact-${type}`,
                artifact_type: type,
                title: artifactPayloads[type].title,
                created_at: '2026-06-01T00:00:00Z',
                source_ids: ['src-material'],
                markdown: `# ${artifactPayloads[type].title}`,
                payload: artifactPayloads[type]
            })),
            total: 6
        })
    }));

    await page.goto('/');

    await page.getByRole('button', { name: /HTTPS 学习卡/ }).click();
    const flashcardStyles = await page.evaluate(() => {
        const flashcard = window.getComputedStyle(document.querySelector('.flashcard')!);
        const quizPanel = window.getComputedStyle(document.querySelector('.quiz-panel')!);
        return { flashcardBackground: flashcard.backgroundImage, quizBackground: quizPanel.backgroundColor };
    });
    expect(luminance(flashcardStyles.flashcardBackground)).toBeLessThan(150);
    expect(luminance(flashcardStyles.quizBackground)).toBeLessThan(150);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /HTTPS 报告/ }).click();
    const reportStyles = await page.evaluate(() => {
        const summary = window.getComputedStyle(document.querySelector('.report-summary')!);
        const section = window.getComputedStyle(document.querySelector('.report-section')!);
        return { summaryBackground: summary.backgroundColor, sectionBackground: section.backgroundColor };
    });
    expect(luminance(reportStyles.summaryBackground)).toBeLessThan(150);
    expect(luminance(reportStyles.sectionBackground)).toBeLessThan(150);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /HTTPS FAQ/ }).click();
    const faqStyles = await page.evaluate(() => window.getComputedStyle(document.querySelector('.faq-item')!).backgroundColor);
    expect(luminance(faqStyles)).toBeLessThan(150);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /协议对比表/ }).click();
    const tableStyles = await page.evaluate(() => {
        const table = window.getComputedStyle(document.querySelector('.data-table-viewer')!);
        const header = window.getComputedStyle(document.querySelector('.data-table-viewer th')!);
        return { tableBackground: table.backgroundColor, headerBackground: header.backgroundColor };
    });
    expect(luminance(tableStyles.tableBackground)).toBeLessThan(150);
    expect(luminance(tableStyles.headerBackground)).toBeLessThan(150);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /HTTPS 信息图/ }).click();
    const infographicStyles = await page.evaluate(() => {
        const frame = window.getComputedStyle(document.querySelector('.infographic-frame')!);
        const section = window.getComputedStyle(document.querySelector('.infographic-section-item')!);
        return { frameBackground: frame.backgroundColor, sectionBackground: section.backgroundColor };
    });
    expect(luminance(infographicStyles.frameBackground)).toBeLessThan(150);
    expect(luminance(infographicStyles.sectionBackground)).toBeLessThan(150);
    await page.getByRole('button', { name: /工作室/ }).click();

    await page.getByRole('button', { name: /视频概览占位/ }).click();
    const placeholderStyles = await page.evaluate(() => {
        const placeholder = window.getComputedStyle(document.querySelector('.placeholder-artifact')!);
        const label = window.getComputedStyle(document.querySelector('.placeholder-label')!);
        return { placeholderBackground: placeholder.backgroundImage, labelBackground: label.backgroundColor };
    });
    expect(luminance(placeholderStyles.placeholderBackground)).toBeLessThan(150);
    expect(luminance(placeholderStyles.labelBackground)).toBeLessThan(150);
});
