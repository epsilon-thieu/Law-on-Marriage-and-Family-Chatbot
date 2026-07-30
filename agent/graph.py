
from __future__ import  annotations

import sys
from pathlib import Path
from contextlib import ExitStack
from typing import Annotated,TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.analyzer import Analyzer, AnalyzerResult
from agent.legal_rag import LegalRagNode
from agent.chit_chat import ChitChatNode
from agent.out_of_scope import OutOfScopeNode

DB_PATH = Path(__file__).parent.parent / "data" / "chat_memory.db"

class GraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    question: str
    analyzer_result: AnalyzerResult
    answer: str
    citations: list[dict]
    num_chunks_used: int


class HNGDAgentGraph:

    def __init__(self):
        print("Đang khởi tạo các node (load model)")
        self.analyzer = Analyzer()
        self.legal_rag_node = LegalRagNode()  # load e5-base + Qdrant + BM25
        self.chit_chat_node = ChitChatNode()
        self.out_of_scope_node = OutOfScopeNode()

        self._exit_stack = ExitStack()
        self.checkpointer = self._exit_stack.enter_context(
            SqliteSaver.from_conn_string(str(DB_PATH))
        )

        self.graph = self._build_graph()


    def _node_analyzer(self, state: GraphState) -> dict:
        result = self.analyzer.analyze(state["question"], history=state.get("messages", []))
        return {"analyzer_result": result}

    def _node_legal_rag(self, state: GraphState) -> dict:
        rag_result = self.legal_rag_node.run(state["question"], state["analyzer_result"])
        g = rag_result.generated
        return {
            "answer": g.answer,
            "citations": g.citations,
            "num_chunks_used": rag_result.num_chunks_used,
            "messages": [("assistant", g.answer)]
        }

    def _node_chit_chat(self, state: GraphState) -> dict:
        answer = self.chit_chat_node.run(state["question"])
        return {"answer": answer,
                "citations": [],
                "num_chunks_used": 0,
                "messages": [("assistant", answer)]}

    def _node_out_of_scope(self, state: GraphState) -> dict:
        answer = self.out_of_scope_node.run(state["question"])
        return {"answer": answer,
                "citations": [],
                "num_chunks_used": 0,
                "messages": [("assistant", answer)]}


    @staticmethod
    def _route(state: GraphState) -> str:
        category = state["analyzer_result"].category
        mapping = {
            "legal_rag": "legal_rag",
            "chit_chat": "chit_chat",
            "out_of_scope": "out_of_scope",
            "web_search": "out_of_scope",
        }
        return mapping.get(category, "out_of_scope")

    def _build_graph(self):
        builder = StateGraph(GraphState)

        builder.add_node("analyzer", self._node_analyzer)
        builder.add_node("legal_rag", self._node_legal_rag)
        builder.add_node("chit_chat", self._node_chit_chat)
        builder.add_node("out_of_scope", self._node_out_of_scope)

        builder.add_edge(START, "analyzer")
        builder.add_conditional_edges(
            "analyzer",
            self._route,
            {"legal_rag": "legal_rag", "chit_chat": "chit_chat", "out_of_scope": "out_of_scope"},
        )
        builder.add_edge("legal_rag", END)
        builder.add_edge("chit_chat", END)
        builder.add_edge("out_of_scope", END)

        return builder.compile(checkpointer=self.checkpointer)

    def run(self, question: str, thread_id: str = "default_session") -> GraphState:
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke(
            {
                "question": question,
                "messages": [("user", question)]
            },
            config=config
        )


# def main():
#     question = " ".join(sys.argv[1:])
#     agent = HNGDAgentGraph()
#
#     print(f"\nĐang xử lý: {question}\n")
#     final_state = agent.run(question)
#
#     analyzer_result = final_state["analyzer_result"]
#     print(f"category : {analyzer_result.category}")
#     print(f"topic    : {analyzer_result.topic}")
#     print(f"\nTrả lời:\n{final_state.get('answer', '')}\n")
#
#     citations = final_state.get("citations", [])
#     if citations:
#         print("Trích dẫn:")
#         for c in citations:
#             meta = c["metadata"]
#             print(f"  [{c['index']}] {meta.get('source')} - Điều {meta.get('dieu')} - Khoản {meta.get('khoan')}")
#

def main():
    agent = HNGDAgentGraph()

    # Giả lập 1 thread_id cố định cho lượt chat hiện tại
    thread_id = "test_session_01"

    print("==================================================")
    print("  CHATBOT TƯ VẤN LUẬT HNGĐ (Gõ 'exit' để thoát)")
    print("==================================================")

    while True:
        question = input("\nBạn: ").strip()
        if not question or question.lower() == "exit":
            print("Tạm biệt!")
            break

        print("\n[Bot đang suy nghĩ...]")
        final_state = agent.run(question, thread_id=thread_id)

        print(f"\nBot: {final_state.get('answer', '')}\n")

        citations = final_state.get("citations", [])
        if citations:
            print(" Trích dẫn pháp lý:")
            for c in citations:
                meta = c["metadata"]
                print(f"   [{c['index']}] {meta.get('source')} - Điều {meta.get('dieu')} - Khoản {meta.get('khoan')}")


if __name__ == "__main__":
    main()