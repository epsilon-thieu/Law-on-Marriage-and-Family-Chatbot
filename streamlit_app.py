import os
import uuid
from datetime import datetime

import streamlit as st

from agent.graph import HNGDAgentGraph

# ----- Cấu hình trang -----
st.set_page_config(
    page_title="Chatbot Luật Hôn nhân & Gia đình",
    page_icon="⚖️",
    layout="wide",
)

# ----- API key -----
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]


# ----- Load agent 1 lần duy nhất -----
@st.cache_resource(show_spinner="Đang khởi tạo mô hình (lần đầu có thể mất 1-2 phút)...")
def load_agent():
    return HNGDAgentGraph()


agent = load_agent()

# ----- Khởi tạo state quản lý nhiều cuộc trò chuyện -----
if "conversations" not in st.session_state:
    st.session_state.conversations = {}  # {conv_id: {"title": str, "messages": list}}

if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None


def new_conversation():
    conv_id = str(uuid.uuid4())
    st.session_state.conversations[conv_id] = {
        "title": "Đoạn chat mới",
        "messages": [],
        "created_at": datetime.now(),
    }
    st.session_state.current_conv_id = conv_id


# Nếu chưa có cuộc trò chuyện nào, tự tạo 1 cái đầu tiên
if not st.session_state.conversations:
    new_conversation()


# ----- Sidebar: danh sách hội thoại -----
with st.sidebar:
    st.title("⚖️ HNGĐ Chatbot")

    if st.button("➕ Đoạn chat mới", use_container_width=True):
        new_conversation()
        st.rerun()

    st.divider()

    # Hiện mới nhất lên trên
    sorted_convs = sorted(
        st.session_state.conversations.items(),
        key=lambda kv: kv[1]["created_at"],
        reverse=True,
    )

    for conv_id, conv in sorted_convs:
        is_current = conv_id == st.session_state.current_conv_id
        label = ("🟢 " if is_current else "") + conv["title"]
        if st.button(label, key=f"conv_{conv_id}", use_container_width=True):
            st.session_state.current_conv_id = conv_id
            st.rerun()


current_conv_id = st.session_state.current_conv_id
current_conv = st.session_state.conversations[current_conv_id]

# ----- Khu vực chat chính -----
st.title("⚖️ Chatbot Luật Hôn nhân & Gia đình")

for msg in current_conv["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("citations"):
            with st.expander("Trích dẫn pháp lý"):
                for c in msg["citations"]:
                    meta = c["metadata"]
                    st.markdown(
                        f"**[{c['index']}]** {meta.get('source')} — "
                        f"Điều {meta.get('dieu')} — Khoản {meta.get('khoan')}"
                    )

if question := st.chat_input("Nhập câu hỏi về Luật Hôn nhân và Gia đình..."):
    # Đặt tiêu đề hội thoại theo câu hỏi đầu tiên
    if not current_conv["messages"]:
        title = question.strip()
        current_conv["title"] = title[:40] + ("..." if len(title) > 40 else "")

    current_conv["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            try:
                # thread_id = current_conv_id -> mỗi cuộc trò chuyện có bộ nhớ LangGraph riêng
                final_state = agent.run(question, thread_id=current_conv_id)
                answer = final_state.get("answer", "Xin lỗi, tôi chưa có câu trả lời.")
                citations = final_state.get("citations", [])
            except Exception as e:
                answer = f"Đã có lỗi xảy ra: {e}"
                citations = []

        st.write(answer)
        if citations:
            with st.expander("Trích dẫn pháp lý"):
                for c in citations:
                    meta = c["metadata"]
                    st.markdown(
                        f"**[{c['index']}]** {meta.get('source')} — "
                        f"Điều {meta.get('dieu')} — Khoản {meta.get('khoan')}"
                    )

    current_conv["messages"].append(
        {"role": "assistant", "content": answer, "citations": citations}
    )
    st.rerun()