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
    page_title="Reddit Posts Insights Viewer",
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
            st.metric("ROI", f"{post['roi_weight']}")
        with col2:
            st.metric("Relevance", f"{post['relevance_score']:.2f}")
        with col3:
            st.metric("Pain Score", f"{post['pain_score']:.2f}")
        with col4:
            st.metric("Emotion", f"{post['emotion_score']:.2f}")
        with col5:
            st.metric("Tech Depth", f"{post['technical_depth_score']:.1f}")
        with col6:
            st.info(post['pain_point'])

    # Title and tags row
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"[{post['title']}](<{post['url']}>)")
    with col2:
        tags_list = [tag.strip() for tag in post['tags'].split(',') if tag.strip()]
        tags_html = "".join(map(lambda tag: f"<span style='background-color: #2196F3; color: white; padding: 2px 6px; border-radius: 8px; font-size: 11px; margin-right: 4px; display: inline-block; margin-bottom: 2px;'>{tag}</span>", tags_list))
        st.markdown(tags_html, unsafe_allow_html=True)

    # Product opportunity section
    if post.get('product_opportunity'):
        st.success(f"💡 **Suggested Solution:** {post['product_opportunity']}")

    # Add some white space
    st.markdown("")

    with st.expander(f"💡 檢視 SaaS 商機提案卡片 - #{post['id']}", expanded=True):
        st.markdown("#### 📝 " + post['title'])
        # Truncate long posts
        body_text = post['body'][:500] + "..." if len(post['body']) > 500 else post['body']
        st.markdown(f"*{body_text}*")

        st.markdown("---")

        # Standard vertical layout with high contrast status blocks - 100% immune to Streamlit columns rendering bugs
        st.markdown("##### 💡 AI 建議的 Micro-SaaS 產品點子")
        idea_val = post.get('micro_saas_idea') or post.get('product_opportunity') or '尚無明確 MVP 提案'
        st.info(idea_val)

        st.markdown("##### 🎯 關鍵付費買家 (Target Buyer)")
        buyer_val = post.get('target_buyer') or post.get('affected_audience') or '泛 B 端/未知'
        st.success(f"**核心決策人**：{buyer_val}")

        st.markdown("##### 💰 付費意願與付費訊號")
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
    st.title("📊 Reddit Posts Insights Viewer")
    st.markdown("Browse and analyze Reddit posts with AI-generated insights")

    # Configuration
    cfg = get_config()
    provider = cfg["ai"]["provider"]
    db_path = cfg["database"]["path"]
    insights_dir = cfg.get("paths", {}).get("batch_responses_dir", "data/batch_responses")

    # Check if files exist
    if not os.path.exists(db_path):
        st.error(f"Database not found at {db_path}")
        return

    if not os.path.exists(insights_dir):
        st.error(f"Insights directory not found at {insights_dir}")
        return

    # Build cache-buster from current data file mtimes.
    insight_files = list(Path(insights_dir).glob("insight_result_*.jsonl"))
    latest_insight_mtime = max((f.stat().st_mtime for f in insight_files), default=0.0)
    data_version = max(os.path.getmtime(db_path), latest_insight_mtime)

    # Load data
    with st.spinner("Loading posts and insights..."):
        try:
            df = load_posts_with_insights(db_path, insights_dir, provider, data_version)
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return

    if df.empty:
        st.warning("No posts with processed insights found.")
        return

    st.success(f"Loaded {len(df)} posts with insights (provider: {provider})")

    # Sidebar filters
    st.sidebar.header("🔧 Filters & Sorting")

    # Score range filters
    st.sidebar.subheader("Score Filters")

    # Helper function to create safe sliders
    def create_safe_slider(label: str, values: pd.Series, key: str = None):
        min_val = float(values.min())
        max_val = float(values.max())

        # Handle case where all values are the same
        if min_val == max_val:
            st.sidebar.write(f"**{label}**: {min_val:.2f} (all posts have same value)")
            return (min_val, max_val)

        return st.sidebar.slider(
            label,
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val),
            step=0.1,
            key=key
        )

    roi_range = create_safe_slider("ROI Range", df['roi_weight'], "roi")
    relevance_range = create_safe_slider("Relevance Score Range", df['relevance_score'], "relevance")
    pain_range = create_safe_slider("Pain Score Range", df['pain_score'], "pain")
    emotion_range = create_safe_slider("Emotion Score Range", df['emotion_score'], "emotion")
    tech_depth_range = create_safe_slider("Technical Depth Range", df['technical_depth_score'], "tech_depth")

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
        "Subreddits",
        options=subreddits,
        default=subreddits
    )

    # Sorting options
    st.sidebar.subheader("Sorting")
    sort_by = st.sidebar.selectbox(
        "Sort by",
        options=['relevance_score', 'pain_score', 'emotion_score', 'technical_depth_score', 'roi_weight', 'created_utc'],
        index=0
    )

    sort_order = st.sidebar.radio(
        "Sort order",
        options=['Descending', 'Ascending'],
        index=0
    )

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
    ascending = sort_order == 'Ascending'
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

    # Display results count
    st.markdown(f"**Showing {len(filtered_df)} of {len(df)} posts**")

    # Pagination
    posts_per_page = 10
    total_pages = (len(filtered_df) + posts_per_page - 1) // posts_per_page

    if total_pages > 1:
        page = st.selectbox("Page", range(1, total_pages + 1), index=0)
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
        st.sidebar.subheader("📈 Summary Stats")
        st.sidebar.metric("Total Posts", len(filtered_df))
        st.sidebar.metric("Avg Relevance", f"{filtered_df['relevance_score'].mean():.2f}")
        st.sidebar.metric("Avg Pain Score", f"{filtered_df['pain_score'].mean():.2f}")
        st.sidebar.metric("Avg Emotion Score", f"{filtered_df['emotion_score'].mean():.2f}")
        st.sidebar.metric("Avg Tech Depth", f"{filtered_df['technical_depth_score'].mean():.2f}")

if __name__ == "__main__":
    main()
