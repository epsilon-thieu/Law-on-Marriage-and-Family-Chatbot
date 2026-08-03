import os
import uuid
from datetime import datetime

import streamlit as st

from agent.graph import HNGDAgentGraph

# ============================================================
# Cấu hình trang
# ============================================================
st.set_page_config(
    page_title="Chatbot Luật Hôn nhân & Gia đình",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----- API key -----
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]

# ============================================================
# Giao diện (CSS)
# ============================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:wght@600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    :root {
        --navy: #17233b;
        --navy-light: #24344f;
        --gold: #c9a15a;
        --gold-light: #e7cd94;
        --paper: #f7f5ef;
        --ink: #1c2530;
    }

    .stApp { background: var(--paper); }

    /* ---------- Ẩn footer/menu mặc định ---------- */
    #MainMenu, footer { visibility: hidden; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--navy) 0%, #10192a 100%);
        border-right: 1px solid #0b1220;
    }
    section[data-testid="stSidebar"] * { color: #eef1f6 !important; }
    section[data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
        text-align: left;
        font-size: 14px;
        padding: 9px 12px;
        transition: all .15s ease;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(201,161,90,0.18);
        border-color: var(--gold);
        color: #fff !important;
    }
    .sidebar-brand {
        font-family: 'Lora', serif;
        font-size: 21px;
        font-weight: 700;
        color: #fff !important;
        letter-spacing: .2px;
        margin-bottom: 2px;
    }
    .sidebar-sub {
        font-size: 12px;
        color: #9aa7bd !important;
        margin-bottom: 14px;
    }
    .sidebar-section-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .08em;
        color: #7d8aa1 !important;
        margin: 14px 0 6px 4px;
        font-weight: 600;
    }

    /* Nút "Đoạn chat mới" nổi bật */
    div[data-testid="stSidebar"] div[data-testid="stButton"]:first-of-type button {
        background: linear-gradient(135deg, var(--gold) 0%, #b8874a 100%) !important;
        color: var(--navy) !important;
        font-weight: 600 !important;
        border: none !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"]:first-of-type button:hover {
        filter: brightness(1.08);
    }

    /* ---------- Header chính ---------- */
    .main-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 18px 22px;
        background: var(--navy);
        border-radius: 16px;
        margin-bottom: 18px;
        box-shadow: 0 4px 18px rgba(23,35,59,0.18);
    }
    .main-header .icon-badge {
        width: 46px; height: 46px;
        border-radius: 12px;
        background: linear-gradient(135deg, var(--gold), #b8874a);
        display: flex; align-items: center; justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
    }
    .main-header h1 {
        font-family: 'Lora', serif;
        color: #fff;
        font-size: 21px;
        margin: 0;
        line-height: 1.25;
    }
    .main-header p {
        color: #b9c2d4;
        font-size: 13px;
        margin: 2px 0 0 0;
    }

    /* ---------- Bong bóng chat ---------- */
    .chat-bubble {
        padding: 13px 17px;
        line-height: 1.65;
        font-size: 15px;
    }
    .user-bubble {
        background: linear-gradient(135deg, var(--navy), var(--navy-light));
        color: #fff;
        border-radius: 16px 16px 4px 16px;
    }
    .assistant-bubble {
        background: #ffffff;
        color: var(--ink);
        border: 1px solid #e9e4d6;
        border-left: 4px solid var(--gold);
        border-radius: 4px 16px 16px 16px;
    }

    /* ---------- Thẻ trích dẫn pháp lý ---------- */
    .citation-card {
        background: #fbf8f0;
        border: 1px solid #ecdfc0;
        border-left: 3px solid var(--gold);
        border-radius: 8px;
        padding: 9px 13px;
        margin-bottom: 8px;
        font-size: 13.5px;
        color: #3c3122;
    }
    .citation-index {
        display: inline-block;
        background: var(--gold);
        color: var(--navy);
        font-weight: 700;
        border-radius: 6px;
        padding: 1px 8px;
        margin-right: 8px;
        font-size: 12px;
    }
    .citation-meta { color: #6b6552; }

    /* ---------- Ô nhập câu hỏi ---------- */
    div[data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
    }

    /* ---------- Empty state / gợi ý câu hỏi ---------- */
    .empty-hero {
        text-align: center;
        padding: 46px 20px 10px 20px;
    }
    .empty-hero .glyph { font-size: 42px; }
    .empty-hero h2 {
        font-family: 'Lora', serif;
        color: var(--navy);
        margin: 8px 0 4px 0;
    }
    .empty-hero p { color: #6d7688; font-size: 14.5px; }

    div[data-testid="stVerticalBlock"] div.suggestion-btn button {
        background: #fff;
        border: 1px solid #e3ddce;
        border-radius: 12px;
        color: var(--ink);
        text-align: left;
        padding: 12px 14px;
        font-size: 13.5px;
        width: 100%;
        transition: all .15s ease;
    }
    div.suggestion-btn button:hover {
        border-color: var(--gold);
        background: #fdf9ef;
    }

    .disclaimer-bar {
        text-align: center;
        color: #8a8f9a;
        font-size: 11.5px;
        padding: 10px 0 4px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Load agent 1 lần duy nhất
# ============================================================
@st.cache_resource(show_spinner="Đang khởi tạo mô hình (lần đầu có thể mất 1-2 phút)...")
def load_agent():
    return HNGDAgentGraph()


agent = load_agent()

# ============================================================
# State quản lý nhiều cuộc trò chuyện
# ============================================================
if "conversations" not in st.session_state:
    st.session_state.conversations = {}  # {conv_id: {"title": str, "messages": list, "created_at": datetime}}

if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


def new_conversation():
    conv_id = str(uuid.uuid4())
    st.session_state.conversations[conv_id] = {
        "title": "Đoạn chat mới",
        "messages": [],
        "created_at": datetime.now(),
    }
    st.session_state.current_conv_id = conv_id


def delete_conversation(conv_id: str):
    st.session_state.conversations.pop(conv_id, None)
    if st.session_state.current_conv_id == conv_id:
        if st.session_state.conversations:
            latest = max(
                st.session_state.conversations.items(),
                key=lambda kv: kv[1]["created_at"],
            )[0]
            st.session_state.current_conv_id = latest
        else:
            new_conversation()


if not st.session_state.conversations:
    new_conversation()

EXAMPLE_QUESTIONS = [
    "Điều kiện để kết hôn hợp pháp tại Việt Nam là gì?",
    "Thủ tục ly hôn thuận tình cần những giấy tờ gì?",
    "Tài sản chung và tài sản riêng trong hôn nhân được xác định thế nào?",
    "Quyền nuôi con sau khi ly hôn được quy định ra sao?",
]

# ============================================================
# Sidebar: danh sách hội thoại
# ============================================================
with st.sidebar:
    st.markdown('<div class="sidebar-brand">⚖️ HNGĐ Chatbot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-sub">Trợ lý tra cứu Luật Hôn nhân &amp; Gia đình</div>',
        unsafe_allow_html=True,
    )

    if st.button("➕  Đoạn chat mới", use_container_width=True):
        new_conversation()
        st.rerun()

    st.markdown('<div class="sidebar-section-label">Lịch sử hội thoại</div>', unsafe_allow_html=True)

    sorted_convs = sorted(
        st.session_state.conversations.items(),
        key=lambda kv: kv[1]["created_at"],
        reverse=True,
    )

    for conv_id, conv in sorted_convs:
        is_current = conv_id == st.session_state.current_conv_id
        label = ("🟢  " if is_current else "💬  ") + conv["title"]
        col_main, col_del = st.columns([5, 1])
        with col_main:
            if st.button(label, key=f"conv_{conv_id}", use_container_width=True):
                st.session_state.current_conv_id = conv_id
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{conv_id}", help="Xóa đoạn chat này"):
                delete_conversation(conv_id)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(f"{len(st.session_state.conversations)} đoạn chat")

current_conv_id = st.session_state.current_conv_id
current_conv = st.session_state.conversations[current_conv_id]


def render_citations(citations):
    if not citations:
        return
    with st.expander(f"📖 Trích dẫn pháp lý ({len(citations)})"):
        for c in citations:
            meta = c["metadata"]
            st.markdown(
                f'<div class="citation-card">'
                f'<span class="citation-index">{c["index"]}</span>'
                f'<span class="citation-meta">{meta.get("source", "")} — '
                f'Điều {meta.get("dieu", "?")} — Khoản {meta.get("khoan", "?")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ============================================================
# Header chính
# ============================================================
st.markdown(
    """
    <div class="main-header">
        <div class="icon-badge">⚖️</div>
        <div>
            <h1>Chatbot Luật Hôn nhân &amp; Gia đình</h1>
            <p>Hỏi đáp nhanh dựa trên văn bản Luật Hôn nhân và Gia đình Việt Nam</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Khu vực chat
# ============================================================
has_messages = len(current_conv["messages"]) > 0

if not has_messages:
    st.markdown(
        """
        <div class="empty-hero">
            <div class="glyph">📜</div>
            <h2>Bắt đầu một câu hỏi mới</h2>
            <p>Ví dụ về những gì bạn có thể hỏi:</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % 2]:
            st.markdown('<div class="suggestion-btn">', unsafe_allow_html=True)
            if st.button(q, key=f"suggestion_{i}", use_container_width=True):
                st.session_state.pending_question = q
            st.markdown("</div>", unsafe_allow_html=True)

for msg in current_conv["messages"]:
    role = msg["role"]
    avatar = "⚖️" if role == "assistant" else "🧑"
    with st.chat_message(role, avatar=avatar):
        bubble_class = "user-bubble" if role == "user" else "assistant-bubble"
        st.markdown(
            f'<div class="chat-bubble {bubble_class}">{msg["content"]}</div>',
            unsafe_allow_html=True,
        )
        if msg.get("citations"):
            render_citations(msg["citations"])

# Câu hỏi từ gợi ý (nếu có) hoặc từ ô nhập
question = st.chat_input("Nhập câu hỏi về Luật Hôn nhân và Gia đình...")
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

if question:
    if not current_conv["messages"]:
        title = question.strip()
        current_conv["title"] = title[:40] + ("..." if len(title) > 40 else "")

    current_conv["messages"].append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(f'<div class="chat-bubble user-bubble">{question}</div>', unsafe_allow_html=True)

    with st.chat_message("assistant", avatar="⚖️"):
        with st.spinner("Đang tra cứu văn bản luật..."):
            try:
                final_state = agent.run(question, thread_id=current_conv_id)
                answer = final_state.get("answer", "Xin lỗi, tôi chưa có câu trả lời.")
                citations = final_state.get("citations", [])
            except Exception as e:
                answer = f"Đã có lỗi xảy ra: {e}"
                citations = []

        st.markdown(f'<div class="chat-bubble assistant-bubble">{answer}</div>', unsafe_allow_html=True)
        render_citations(citations)

    current_conv["messages"].append(
        {"role": "assistant", "content": answer, "citations": citations}
    )
    st.rerun()

st.markdown(
    '<div class="disclaimer-bar">⚖️ Thông tin do chatbot cung cấp chỉ mang tính tham khảo, '
    'không thay thế tư vấn pháp lý chính thức từ luật sư.</div>',
    unsafe_allow_html=True,
)