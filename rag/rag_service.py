
"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from model.model_factory import chat_model
from langchain_core.runnables import RunnableWithMessageHistory
from rag.file_history_store import FileChatMessageHistory
from utils.path_tool import get_abs_path
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def get_rag_history(session_id: str) -> FileChatMessageHistory:
    """RAG 总结链路的独立会话记忆（chat_history/rag 子目录），
    与主 Agent 的会话记忆文件分离，避免两条链路写同一文件导致历史重复、相互污染"""
    return FileChatMessageHistory(session_id, get_abs_path("chat_history/rag"))


def print_prompt(prompt):
    print("="*20)
    print(prompt.to_string())
    print("="*20)
    return prompt


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        # self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt_text),
                ("system", "以下是用户与助手的对话历史，请结合历史保持多轮对话连贯，优先响应用户最新提问："),
                MessagesPlaceholder("history"),  # 获取历史对话
                ("user", "请回答用户提问：{input}")
            ]
        )
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):

        base_chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        chain = RunnableWithMessageHistory(
            base_chain,
            get_rag_history,                    # 历史存取工厂（独立目录）
            input_messages_key="input",         # 输入中"当前用户消息"字段
            history_messages_key="history"      # 输入中"历史对话"字段
        )
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    # 用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
    def rag_summarize(self, query: str, session_id: str="user1") -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"
        session_config = {
            "configurable": {
                "session_id": session_id,
            }
        }

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            },
            session_config
        )


if __name__ == '__main__':
    rag = RagSummarizeService()

    print(rag.rag_summarize("小户型适合哪些扫地机器人", session_id="test_session"))
