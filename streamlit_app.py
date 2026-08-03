import os
import uuid

import streamlit as st

from agent.graph import HNGDAgentGraph

# ----- Cấu hình trang -----
st.set_page_config(page_title="Chatbot Luật Hôn nhân & Gia đình", page_icon="⚖️")
st.title("⚖️ Chatbot Luật Hôn nhân & Gia đình")

# ----- Nạp API key từ Streamlit Secrets vào biến môi trường -----
# (code trong agent/legal_rag.py hay chỗ khác đọc os.environ["GOOGLE_API_KEY"]
#  thì dòng này đảm bảo key có sẵn trước khi model được gọi)
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]


# ----- Load agent 1 lần duy nhất, dùng lại cho mọi user/session -----
@st.cache_resource(show_spinner="Đang khởi tạo mô hình (lần đầu có thể mất 1-2 phút)...")
def load_agent():
    return HNGDAgentGraph()


agent = load_agent()

# ----- Mỗi tab trình duyệt = 1 thread_id riêng, để lịch sử chat không lẫn giữa các user -----
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # chỉ để hiển thị UI; bộ nhớ thật nằm trong SqliteSaver

# ----- Hiển thị lịch sử chat đã có trong session -----
for msg in st.session_state.messages:
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

# ----- Ô nhập câu hỏi -----
if question := st.chat_input("Nhập câu hỏi về Luật Hôn nhân và Gia đình..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            try:
                final_state = agent.run(question, thread_id=st.session_state.thread_id)
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

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "citations": citations}
    )