import streamlit as st
import sqlite3
import json
import pandas as pd
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Ensure project root is importable when running via `streamlit run gui/gui.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config_loader import get_config

# Configure Streamlit page
st.set_page_config(
    page_title="Reddit 貼文商機探測器 (Reddit Posts Insights Viewer)",
    page_icon="📊",
    layout="wide"
)

def _extract_json_from_text(text: str) -> str:
    """Extract JSON payload from markdown-fenced or plain text."""
    if not text:
        return text

    stripped = text.strip()

    # Fenced block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # First object/array fallback
    match = re.search(r"[\{\[].*[\}\]]", stripped, re.DOTALL)
    if match:
        return match.group(0).strip()

    return stripped


@st.cache_data
def load_posts_with_insights(
    db_path: str,
    insights_dir: str,
    provider: str,
    data_version: float
) -> pd.DataFrame:
    """Load posts with insight_processed=1 and join with insight data."""

    # Connect to SQLite database
    conn = sqlite3.connect(db_path)

    # Query posts with insights processed
    query = """
    SELECT id, url, title, body, relevance_score, pain_score, emotion_score,
           COALESCE(technical_depth_score, 0) as technical_depth_score,
           subreddit, created_utc, processed_at,
           willingness_to_pay, existing_workarounds, micro_saas_idea, target_buyer
    FROM posts
    WHERE insight_processed = 1
    """

    posts_df = pd.read_sql_query(query, conn)
    conn.close()

    # Load insight data from JSONL files
    insights_data = {}
    insights_path = Path(insights_dir)

    for jsonl_file in insights_path.glob("insight_result_*.jsonl"):
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    custom_id = data.get('custom_id')
                    if not custom_id:
                        continue

                    if provider == "anthropic" or provider in ("gemini", "deepseek"):
                        # Custom simulated adapters reuse Anthropic JSONL format
                        if data.get("result_type") != "succeeded":
                            continue
                        content = data.get("content", "")
                        insight_json = json.loads(_extract_json_from_text(content))
                        insights_data[custom_id] = insight_json
                    elif provider == "openai":
                        # OpenAI format
                        if (
                            data.get('response') and
                            data['response'].get('body') and
                            data['response']['body'].get('choices')
                        ):
                            content = data['response']['body']['choices'][0]['message']['content']
                            insight_json = json.loads(_extract_json_from_text(content))
                            insights_data[custom_id] = insight_json

                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    # Add insight data to posts dataframe
    posts_df['pain_point'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('pain_point', ''))
    posts_df['tags'] = posts_df['id'].map(lambda x: ', '.join(insights_data.get(x, {}).get('tags', [])))
    posts_df['roi_weight'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('roi_weight', 0))
    posts_df['justification'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('justification', ''))
    posts_df['product_opportunity'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('product_opportunity', ''))
    posts_df['affected_audience'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('affected_audience', ''))
    posts_df['existing_alternatives'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('existing_alternatives', ''))
    posts_df['build_complexity'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('build_complexity', ''))
    posts_df['technical_moat'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('technical_moat', ''))
    posts_df['business_model'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('business_model', ''))
    posts_df['business_type'] = posts_df['id'].map(lambda x: insights_data.get(x, {}).get('business_type', ''))

    # Load new SaaS market insights columns (fall back to JSONL first, then DB columns)
    for col in ('willingness_to_pay', 'existing_workarounds', 'micro_saas_idea', 'target_buyer'):
        posts_df[col] = posts_df.apply(
            lambda row: insights_data.get(row['id'], {}).get(col, row.get(col, '')),
            axis=1
        )

    return posts_df

def display_post_card(post: pd.Series):
    """Display a single post as a card."""
    with st.container():
        st.markdown("---")
        # Header with title and scores
        col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 9])

        with col1:
            st.metric("ROI 評估", f"{post['roi_weight']}")
        with col2:
            st.metric("關聯度 (Relevance)", f"{post['relevance_score']:.2f}")
        with col3:
            st.metric("痛點分數 (Pain)", f"{post['pain_score']:.2f}")
        with col4:
            st.metric("情感強度 (Emotion)", f"{post['emotion_score']:.2f}")
        with col5:
            st.metric("技術深度 (Tech Depth)", f"{post['technical_depth_score']:.1f}")
        with col6:
            st.info(post['pain_point'])

    # Title and tags row
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"**🔗 貼文原網址**：[{post['title']}](<{post['url']}>)")
    with col2:
        tags_list = [tag.strip() for tag in post['tags'].split(',') if tag.strip()]
        tags_html = "".join(map(lambda tag: f"<span style='background-color: #2196F3; color: white; padding: 2px 6px; border-radius: 8px; font-size: 11px; margin-right: 4px; display: inline-block; margin-bottom: 2px;'>{tag}</span>", tags_list))
        st.markdown(tags_html, unsafe_allow_html=True)

    # Product opportunity section
    if post.get('product_opportunity'):
        st.success(f"💡 **建議的解決方案 (MVP Solution):** {post['product_opportunity']}")

    # Add some white space
    st.markdown("")

    with st.expander(f"💡 檢視 SaaS 商機提案卡片 - #{post['id']}", expanded=True):
        st.markdown("#### 📝 貼文原標題：" + post['title'])
        # Truncate long posts
        body_text = post['body'][:500] + "..." if len(post['body']) > 500 else post['body']
        st.markdown(f"*原貼文內文：{body_text}*")

        st.markdown("---")

        # Standard vertical layout with high contrast status blocks - 100% immune to Streamlit columns rendering bugs
        st.markdown("##### 💡 AI 建議的 Micro-SaaS 產品點子 (Micro-SaaS Idea)")
        idea_val = post.get('micro_saas_idea') or post.get('product_opportunity') or '尚無明確 MVP 提案'
        st.info(idea_val)

        st.markdown("##### 🎯 關鍵付費買家 (Target Buyer)")
        buyer_val = post.get('target_buyer') or post.get('affected_audience') or '泛 B 端/未知'
        st.success(f"**核心決策人**：{buyer_val}")

        st.markdown("##### 💰 付費意願與付費訊號 (Willingness to Pay)")
        wtp_val = post.get('willingness_to_pay') or '尚無分析到具體預算或高昂的時間成本抱怨'
        st.warning(wtp_val)

        st.markdown("##### 🛠️ 現有解決笨方法 (Workarounds)")
        workarounds_val = post.get('existing_workarounds') or post.get('existing_alternatives') or '尚無描述'
        st.markdown(f"> *{workarounds_val}*")

        if post['justification']:
            st.markdown("---")
            st.markdown(f"**可行性評估 (Justification):** {post['justification']}")

        # Render technical moat and monetization details
        st.markdown("---")
        st.markdown(f"🛡️ **技術複製壁壘 (Technical Moat):** {post.get('technical_moat', '無')}")
        st.markdown(f"📊 **商業變現模型 (Business Model):** {post.get('business_model', '無')} | **開發複雜度:** {post.get('build_complexity', '無')}")

def main():
    st.title("📊 Reddit 貼文商機探測器 (Reddit Posts Insights Viewer)")
    st.markdown("瀏覽並分析 Reddit 中高價值的 B 端商機與痛點 (AI-Generated Micro-SaaS Insights)")

    # Configuration
    cfg = get_config()
    provider = cfg["ai"]["provider"]
    db_path = cfg["database"]["path"]
    insights_dir = cfg.get("paths", {}).get("batch_responses_dir", "data/batch_responses")

    # Check if files exist
    if not os.path.exists(db_path):
        st.error(f"找不到資料庫：{db_path}")
        return

    if not os.path.exists(insights_dir):
        st.error(f"找不到 AI 分析目錄：{insights_dir}")
        return

    # Build cache-buster from current data file mtimes.
    insight_files = list(Path(insights_dir).glob("insight_result_*.jsonl"))
    latest_insight_mtime = max((f.stat().st_mtime for f in insight_files), default=0.0)
    data_version = max(os.path.getmtime(db_path), latest_insight_mtime)

    # Load data
    with st.spinner("載入貼文與 AI 商機提案中..."):
        try:
            df = load_posts_with_insights(db_path, insights_dir, provider, data_version)
        except Exception as e:
            st.error(f"資料加載失敗：{str(e)}")
            return

    if df.empty:
        st.warning("資料庫中尚無已完成分析的商機。請先執行 python main.py 進行爬取與分析！")
        return

    st.success(f"🎉 成功加載 {len(df)} 篇商機提案！(分析引擎: {provider})")

    # Sidebar filters
    st.sidebar.header("🔧 篩選器與排序 (Filters & Sorting)")

    # Score range filters
    st.sidebar.subheader("分數過濾器 (Score Filters)")

    # Helper function to create safe sliders with custom absolute bounds and high precision
    def create_safe_slider(label: str, values: pd.Series, min_abs: float = 0.0, max_abs: float = 10.0, step: float = 0.01, key: str = None):
        min_val = float(values.min()) if not values.empty else min_abs
        max_val = float(values.max()) if not values.empty else max_abs

        # Ensure bounds cover both data range and desired absolute range
        min_boundary = min(min_abs, min_val)
        max_boundary = max(max_abs, max_val)

        return st.sidebar.slider(
            label,
            min_value=float(min_boundary),
            max_value=float(max_boundary),
            value=(float(min_val), float(max_val)),
            step=step,
            format="%.2f",
            key=key
        )

    roi_range = create_safe_slider("ROI 權重範圍", df['roi_weight'], min_abs=0.0, max_abs=5.0, step=0.01, key="roi")
    relevance_range = create_safe_slider("關聯度範圍", df['relevance_score'], min_abs=0.0, max_abs=10.0, step=0.01, key="relevance")
    pain_range = create_safe_slider("痛點強度範圍", df['pain_score'], min_abs=0.0, max_abs=10.0, step=0.01, key="pain")
    emotion_range = create_safe_slider("情感強度範圍", df['emotion_score'], min_abs=0.0, max_abs=10.0, step=0.01, key="emotion")
    tech_depth_range = create_safe_slider("技術深度範圍", df['technical_depth_score'], min_abs=0.0, max_abs=10.0, step=0.01, key="tech_depth")

    # High Willingness to Pay Filter
    st.sidebar.subheader("🎯 商業信號過濾")
    show_high_wtp_only = st.sidebar.checkbox(
        "只顯示強烈付費意願的點子",
        value=False,
        help="過濾僅顯示 AI 成功挖掘到具體花費、時間浪費、或成本抱怨等付費意願訊號的商機卡片。"
    )

    # Subreddit filter
    subreddits = df['subreddit'].unique().tolist()
    selected_subreddits = st.sidebar.multiselect(
        "來源看板 (Subreddits)",
        options=subreddits,
        default=subreddits
    )

    # Sorting options
    st.sidebar.subheader("排序規則 (Sorting)")
    sort_by_mapping = {
        'relevance_score': '關聯度分數 (Relevance)',
        'pain_score': '痛點強度分數 (Pain)',
        'emotion_score': '情感強度分數 (Emotion)',
        'technical_depth_score': '技術深度分數 (Tech Depth)',
        'roi_weight': 'ROI 投資回報率',
        'created_utc': '貼文發布時間 (Created)'
    }
    
    sort_by_display = st.sidebar.selectbox(
        "排序依據",
        options=list(sort_by_mapping.values()),
        index=0
    )
    # Get the raw column name from the display name
    sort_by = [k for k, v in sort_by_mapping.items() if v == sort_by_display][0]

    sort_order = st.sidebar.radio(
        "排序順序",
        options=['降冪 (Descending)', '升冪 (Ascending)'],
        index=0
    )

    # 🚀 Execution Control Console in Sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🚀 全自動控制台 (Control Console)")
    st.sidebar.markdown("您可以直接在網頁上一鍵啟動 Reddit 爬蟲與 DeepSeek-R1 分析管線。")
    
    if st.sidebar.button("⚙️ 啟動全自動爬蟲與 AI 分析", help="點擊自動調用 Playwright 爬蟲與 R1 推理模型"):
        with st.spinner("正在啟動 Playwright 前往 Reddit 爬取並調用 DeepSeek-R1 提取商機中... 這可能需要 2-5 分鐘，請稍候"):
            try:
                # Dynamically import and run the runner pipeline
                from scheduler.runner import run_daily_pipeline
                run_daily_pipeline()
                
                st.sidebar.success("🎉 管線執行完畢！最新商機已自動載入！")
                # Clear Streamlit cache to load fresh SQLite rows and rerun page
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ 管線執行失敗：{str(e)}")

    # Apply filters
    filtered_df = df[
        (df['roi_weight'] >= roi_range[0]) &
        (df['roi_weight'] <= roi_range[1]) &
        (df['relevance_score'] >= relevance_range[0]) &
        (df['relevance_score'] <= relevance_range[1]) &
        (df['pain_score'] >= pain_range[0]) &
        (df['pain_score'] <= pain_range[1]) &
        (df['emotion_score'] >= emotion_range[0]) &
        (df['emotion_score'] <= emotion_range[1]) &
        (df['technical_depth_score'] >= tech_depth_range[0]) &
        (df['technical_depth_score'] <= tech_depth_range[1]) &
        (df['subreddit'].isin(selected_subreddits))
    ]

    # Apply High Willingness to Pay Filter
    if show_high_wtp_only:
        filtered_df = filtered_df[
            filtered_df['willingness_to_pay'].notna() &
            (filtered_df['willingness_to_pay'].str.strip() != "") &
            (~filtered_df['willingness_to_pay'].str.contains("尚無", case=False, na=False))
        ]

    # Apply sorting
    ascending = '升冪' in sort_order
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

    # Display results count
    st.markdown(f"**目前顯示第 {len(filtered_df)} 筆，共 {len(df)} 筆商機提案**")

    # Pagination
    posts_per_page = 10
    total_pages = (len(filtered_df) + posts_per_page - 1) // posts_per_page

    if total_pages > 1:
        page = st.selectbox("分頁 (Page)", range(1, total_pages + 1), index=0)
        start_idx = (page - 1) * posts_per_page
        end_idx = start_idx + posts_per_page
        page_df = filtered_df.iloc[start_idx:end_idx]
    else:
        page_df = filtered_df

    # Display posts
    for idx, post in page_df.iterrows():
        display_post_card(post)

    # Summary statistics
    if len(filtered_df) > 0:
        st.sidebar.subheader("📈 全局數據總覽 (Summary Stats)")
        st.sidebar.metric("篩選後商機總數", len(filtered_df))
        st.sidebar.metric("平均關聯度", f"{filtered_df['relevance_score'].mean():.2f}")
        st.sidebar.metric("平均痛點分數", f"{filtered_df['pain_score'].mean():.2f}")
        st.sidebar.metric("平均情感強度", f"{filtered_df['emotion_score'].mean():.2f}")
        st.sidebar.metric("平均技術深度", f"{filtered_df['technical_depth_score'].mean():.2f}")

if __name__ == "__main__":
    main()
