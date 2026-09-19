from abc import ABC, abstractmethod
import os
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from utils.config_handler import rag_conf

# 校验 .env 注入的 DashScope Key
if not os.getenv("DASHSCOPE_API_KEY"):
    raise RuntimeError("未配置 DASHSCOPE_API_KEY：请在项目根目录 .env 中填写后重新启动")

# 模型工厂
class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


# 聊天模型
class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return ChatTongyi(model=rag_conf["chat_model_name"])

# 嵌入模型
class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])

# 创建模型实例
chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()
