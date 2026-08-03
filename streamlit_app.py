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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lora:wght@600;700&display=swap');

    /* ------------------------------------------------------
       QUAN TRỌNG: Streamlit dùng các biến CSS này (--text-color,
       --background-color, --secondary-background-color) cho MỌI
       widget mặc định (nút bấm, ô nhập, expander, spinner...).
       Nếu trình duyệt/hệ điều hành người dùng bật dark mode,
       Streamlit tự đổi các biến này sang tối, khiến chữ tối trên
       nền tối do ta tự vẽ -> chữ "biến mất". Ép các biến này về
       sáng ngay từ đầu để mọi widget mặc định luôn tương phản tốt.
       ------------------------------------------------------ */
    :root, .stApp {
        --background-color: #eef1f8 !important;
        --secondary-background-color: #ffffff !important;
        --text-color: #0f172a !important;
        --primary-color: #4338ca !important;
        color-scheme: light !important;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    :root {
        --ink:        #0f172a;
        --ink-soft:   #475569;
        --indigo:     #4338ca;
        --indigo-dk:  #312e81;
        --amber:      #f59e0b;
        --amber-dk:   #b45309;
        --green:      #16a34a;
        --green-dk:   #15803d;
        --bg:         #eef1f8;
        --card:       #ffffff;
        --border:     #e2e6f0;
    }

    .stApp {
        background:
            radial-gradient(circle at 8% 0%, rgba(67,56,202,0.10), transparent 45%),
            radial-gradient(circle at 95% 15%, rgba(245,158,11,0.12), transparent 40%),
            var(--bg);
    }

    #MainMenu, footer { visibility: hidden; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] * { color: #f1f5f9 !important; }
    section[data-testid="stSidebar"] .stButton button {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        text-align: left;
        font-size: 14px;
        font-weight: 500;
        padding: 10px 13px;
        transition: all .15s ease;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: #334155;
        border-color: var(--amber);
    }
    .sidebar-brand {
        font-family: 'Lora', serif;
        font-size: 22px;
        font-weight: 700;
        color: #ffffff !important;
        display: flex; align-items: center; gap: 8px;
        margin-bottom: 2px;
    }
    .sidebar-sub {
        font-size: 12.5px;
        color: #94a3b8 !important;
        margin-bottom: 16px;
    }
    .sidebar-section-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .09em;
        color: #64748b !important;
        margin: 18px 0 8px 2px;
        font-weight: 700;
    }

    /* Nút "Đoạn chat mới" nổi bật rõ */
    div[data-testid="stSidebar"] div[data-testid="stButton"]:first-of-type button {
        background: linear-gradient(135deg, var(--amber) 0%, var(--amber-dk) 100%) !important;
        color: #1a1100 !important;
        font-weight: 700 !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(245,158,11,0.35);
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"]:first-of-type button:hover {
        filter: brightness(1.07);
    }

    /* ---------- Cuộc trò chuyện đang mở: highlight XANH LÁ ---------- */
    div[class*="st-key-conv_current"] button {
        background: linear-gradient(135deg, var(--green) 0%, var(--green-dk) 100%) !important;
        border: 1px solid var(--green-dk) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(22,163,74,0.35);
    }
    div[class*="st-key-conv_current"] button:hover {
        filter: brightness(1.08);
    }

    /* ---------- Header chính (hero) ---------- */
    .main-header {
        display: flex;
        align-items: center;
        gap: 18px;
        padding: 26px 28px;
        background: linear-gradient(120deg, var(--indigo) 0%, var(--indigo-dk) 100%);
        border-radius: 20px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(49,46,129,0.28);
    }
    .main-header .icon-badge {
        width: 56px; height: 56px;
        border-radius: 16px;
        background: var(--amber);
        display: flex; align-items: center; justify-content: center;
        font-size: 26px;
        flex-shrink: 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .main-header h1, .main-header h1 * { color: #ffffff !important; }
    .main-header h1 {
        font-family: 'Lora', serif;
        font-size: 24px;
        margin: 0;
        line-height: 1.3;
    }
    .main-header p, .main-header p * { color: #e4e1ff !important; }
    .main-header p {
        font-size: 13.5px;
        margin: 4px 0 0 0;
        font-weight: 500;
    }

    /* ---------- Bong bóng chat ---------- */
    .chat-bubble { padding: 14px 18px; line-height: 1.7; font-size: 15.5px; }
    .user-bubble, .user-bubble * { color: #ffffff !important; }
    .user-bubble {
        background: var(--indigo);
        border-radius: 18px 18px 4px 18px;
        box-shadow: 0 3px 10px rgba(67,56,202,0.25);
    }
    .assistant-bubble, .assistant-bubble * { color: var(--ink) !important; }
    .assistant-bubble {
        background: var(--card);
        border: 1px solid var(--border);
        border-left: 5px solid var(--amber);
        border-radius: 4px 18px 18px 18px;
        box-shadow: 0 3px 10px rgba(15,23,42,0.06);
    }

    /* ---------- Hộp mở rộng (expander) chứa trích dẫn ---------- */
    div[data-testid="stExpander"],
    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {
        background: var(--card) !important;
    }
    div[data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        overflow: hidden;
    }
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] summary *,
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary p {
        color: var(--ink) !important;
        font-weight: 600 !important;
    }
    div[data-testid="stExpander"] svg { fill: var(--ink) !important; }
    div[data-testid="stExpanderDetails"],
    div[data-testid="stExpanderDetails"] * {
        color: var(--ink) !important;
        background: var(--card) !important;
    }

    /* ---------- Thẻ trích dẫn pháp lý ---------- */
    .citation-card, .citation-card * { color: #78350f !important; }
    .citation-card {
        background: #fffbeb !important;
        border: 1px solid #fde68a;
        border-left: 4px solid var(--amber);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 13.5px;
    }
    .citation-index, .citation-index * {
        display: inline-block;
        background: var(--amber) !important;
        color: #1a1100 !important;
        font-weight: 800;
        border-radius: 6px;
        padding: 1px 9px;
        margin-right: 9px;
        font-size: 12px;
    }
    .citation-meta, .citation-meta * { font-weight: 500; }

    /* ---------- Ô nhập câu hỏi ---------- */
    div[data-testid="stChatInput"] {
        background: var(--card) !important;
        border-radius: 16px !important;
        box-shadow: 0 6px 18px rgba(15,23,42,0.08);
    }
    div[data-testid="stChatInput"] textarea {
        background: var(--card) !important;
        color: var(--ink) !important;
        border-radius: 14px !important;
        border: 1.5px solid var(--border) !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder { color: #94a3b8 !important; }

    /* ---------- Trạng thái đang tải / spinner ---------- */
    div[data-testid="stSpinner"], div[data-testid="stSpinner"] * {
        color: var(--ink) !important;
        font-weight: 500;
    }

    /* ---------- Empty state / gợi ý câu hỏi ---------- */
    .empty-hero { text-align: center; padding: 40px 20px 16px 20px; }
    .empty-hero .glyph {
        font-size: 46px;
        display: inline-block;
        background: linear-gradient(135deg, var(--indigo), var(--amber));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .empty-hero h2, .empty-hero h2 * { color: var(--ink) !important; }
    .empty-hero h2 { font-family: 'Lora', serif; margin: 10px 0 4px 0; font-size: 22px; }
    .empty-hero p, .empty-hero p * { color: var(--ink-soft) !important; }
    .empty-hero p { font-size: 14.5px; }

    /* ---------- Nút câu hỏi gợi ý (targeted qua st.container(key=...)) ---------- */
    div[class*="st-key-suggestion_"] { position: relative; z-index: 1; }
    div[class*="st-key-suggestion_"] button {
        background: #ffffff !important;
        color: var(--ink) !important;
        border: 1.5px solid var(--border) !important;
        border-radius: 14px !important;
        text-align: left !important;
        padding: 16px 18px !important;
        font-size: 14.5px !important;
        font-weight: 500 !important;
        width: 100%;
        box-shadow: 0 2px 8px rgba(15,23,42,0.05);
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s ease;
    }
    div[class*="st-key-suggestion_"] button:hover,
    div[class*="st-key-suggestion_"] button:focus {
        border-color: var(--indigo) !important;
        background-color: #f5f3ff !important;
        color: var(--indigo-dk) !important;
        transform: scale(1.045);
        box-shadow: 0 12px 26px rgba(67,56,202,0.22);
        z-index: 5;
        position: relative;
    }
    div[class*="st-key-suggestion_"] button:active {
        color: var(--indigo-dk) !important;
        background-color: #f5f3ff !important;
    }

    .disclaimer-bar, .disclaimer-bar * { color: var(--ink-soft) !important; }
    .disclaimer-bar {
        text-align: center;
        font-size: 12px;
        padding: 14px 0 4px 0;
        border-top: 1px solid var(--border);
        margin-top: 10px;
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
    ("💍", "Điều kiện để kết hôn hợp pháp tại Việt Nam là gì?"),
    ("📄", "Thủ tục ly hôn thuận tình cần những giấy tờ gì?"),
    ("🏠", "Tài sản chung và tài sản riêng trong hôn nhân được xác định thế nào?"),
    ("👨‍👩‍👧", "Quyền nuôi con sau khi ly hôn được quy định ra sao?"),
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
        # "conv_current" chỉ dùng cho ĐÚNG MỘT hội thoại tại một thời điểm
        # -> an toàn để dùng làm key cố định, CSS bên trên sẽ tô xanh lá.
        row_key = "conv_current" if is_current else f"conv_row_{conv_id}"
        label = ("✅  " if is_current else "💬  ") + conv["title"]
        with st.container(key=row_key):
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
            <p>Chọn một câu hỏi mẫu bên dưới, hoặc gõ câu hỏi của riêng bạn</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (icon, q) in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % 2]:
            with st.container(key=f"suggestion_{i}"):
                if st.button(f"{icon}  {q}", key=f"suggestion_btn_{i}", use_container_width=True):
                    st.session_state.pending_question = q

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