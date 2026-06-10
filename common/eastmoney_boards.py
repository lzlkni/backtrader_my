#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Playwright 从东方财富网页抓取热门概念板块
绕过 API 限流问题，直接获取浏览器渲染的数据
"""

import json
import sys
import re


def get_hot_concept_boards(top_n=5, headless=True):
    """
    从东方财富网页抓取热门概念板块

    返回: [{'code':'BK0949', 'name':'氦气概念', 'change_pct':3.41}, ...]
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[ERROR] playwright 未安装，请运行: pip install playwright && playwright install chromium', file=sys.stderr)
        return []

    boards = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = context.new_page()

        try:
            page.goto(
                'https://quote.eastmoney.com/center/boardlist.html#concept_board',
                wait_until='domcontentloaded',
                timeout=30000
            )

            # 等待页面加载完成 - 先等待基本的 DOM 加载
            page.wait_for_load_state('networkidle', timeout=30000)

            # 尝试多种选择器
            for selector in ['.data-table', '#table_list_table', '.table', 'table.dataview-table']:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    print(f'[INFO] Found table with selector: {selector}', file=sys.stderr)
                    break
                except:
                    continue

            # 截图调试
            page.screenshot(path='debug_eastmoney.png', full_page=True)
            print('[INFO] Screenshot saved to debug_eastmoney.png', file=sys.stderr)

            # 使用 JavaScript 直接提取数据 - 尝试多种表格结构
            rows_data = page.evaluate('''() => {
                // 尝试找到表格
                const tables = document.querySelectorAll('table');
                let targetTable = null;

                for (const table of tables) {
                    const rows = table.querySelectorAll('tbody tr');
                    if (rows.length > 5) {
                        targetTable = table;
                        break;
                    }
                }

                if (!targetTable) {
                    // 尝试使用通用选择器
                    const allRows = document.querySelectorAll('tbody tr');
                    if (allRows.length > 5) {
                        targetTable = allRows[0].closest('table');
                    }
                }

                if (!targetTable) return [];

                const rows = targetTable.querySelectorAll('tbody tr');
                const result = [];

                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 4) {
                        const nameCell = cells[1];
                        const codeCell = cells[2];
                        const changeCell = cells[3];

                        // 提取板块名称
                        const nameLink = nameCell.querySelector('a');
                        const name = nameLink ? nameLink.textContent.trim() : nameCell.textContent.trim();

                        // 提取板块代码
                        const codeLink = codeCell.querySelector('a');
                        let code = '';
                        if (codeLink) {
                            const href = codeLink.getAttribute('href') || '';
                            const match = href.match(/BK\\d+/);
                            if (match) code = match[0];
                        }
                        if (!code) {
                            code = codeCell.textContent.trim();
                        }

                        // 提取涨跌幅
                        const changeText = changeCell.textContent.trim().replace('%', '');
                        const changePct = parseFloat(changeText);

                        if (name && code && !isNaN(changePct)) {
                            result.push({
                                name: name,
                                code: code,
                                change_pct: changePct
                            });
                        }
                    }
                });

                return result;
            }''')

            # 按涨跌幅降序排序
            rows_data.sort(key=lambda x: x['change_pct'], reverse=True)
            boards = rows_data[:top_n]

        except Exception as e:
            print(f'[ERROR] 抓取失败: {e}', file=sys.stderr)

        finally:
            browser.close()

    return boards


if __name__ == '__main__':
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    result = get_hot_concept_boards(top_n=top_n)
    print(json.dumps(result, ensure_ascii=False))
