import subprocess
from pathlib import Path
from typing import List, Dict, Any
from pymilvus import (
    connections, FieldSchema, CollectionSchema,
    DataType, Collection, utility, Function,
    FunctionType, AnnSearchRequest,RRFRanker
)
import time
from adapters.vectordb.base_vector_db import BaseVectorDBAdapter
from utils.text_processing import TextProcessor

class MilvusAdapter(BaseVectorDBAdapter):
    """Milvus向量数据库适配器，封装所有向量数据库操作"""
    
    _DOCKER_CMD = ["docker", "info"]
    _MILVUS_START_CWD = "../../utils/milvus_standalone_docker"
    _MILVUS_START_CMD = ["powershell.exe", "-Command", "./standalone.bat start"]

    def __init__(self, config = Dict[str,Any],codebase_path=None):
        """
        初始化向量数据库适配器
        :param codebase_path: 知识库路径，默认当前目录
        :param config: 知识库配置
        """

        super().__init__(config,codebase_path)
        self.text_processor = TextProcessor()
        self._init_components()
    
    def get_search_params(self, search_type: str) -> dict:
        """暴露适配器专属参数"""
        return self.config["search_params"][search_type]
    
    def _init_components(self):
        """初始化核心组件"""
        self._start_services()
        if utility.has_collection(self.config['collection_name']):
            self.collection = Collection(self.config['collection_name'])
        else:
            self.collection = self._setup_collection()
            self._load_knowledge_base()
        
    def _wait_for_milvus_ready(self, timeout=30):
        """等待Milvus服务完全启动"""
        start_time = time.time()
        while True:
            try:
                # 尝试执行简单操作（如获取集合列表）
                print("Milvus版本:", utility.get_server_version())
                print("✅ Milvus服务已就绪！")
                return
            except Exception as e:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(f"Milvus服务启动超时（{timeout}s）") from e
                print(f"⏳ 等待Milvus启动中... 错误: {str(e)}，剩余时间: {timeout - elapsed:.1f}s")
                time.sleep(2)
    def _start_services(self):
        """启动依赖服务"""
        if not self._is_docker_running():
            self._start_docker()
        
        try:
            script_dir = Path(__file__).resolve().parent
            cwd_path = (
                    script_dir/ self._MILVUS_START_CWD  # 调整路径层级
            ).resolve()
            print(f"[Milvus] standlong服务执行目录: {cwd_path}")  # 调试输出
            subprocess.run(self._MILVUS_START_CMD,cwd=cwd_path, check=True,encoding="utf-8" )
            connections.connect("default", host=self.config["host"], port=self.config["port"])

            print("当前集合列表:", utility.list_collections())
            self._wait_for_milvus_ready()
            print("[Milvus] 服务已启动")
        except subprocess.CalledProcessError as e:
            print(f"[Error] 服务启动失败: {str(e)}")
            raise RuntimeError("Milvus服务启动失败") from e

    def _setup_collection(self) -> Collection:
        """配置Milvus集合"""
        """如果已经存在该集合，则直接返回"""
        if utility.has_collection(self.config['collection_name']):
            utility.drop_collection(self.config['collection_name'])
        # 定义数据结构
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, 
                      dim=self.text_processor.model.get_sentence_embedding_dimension()),
            FieldSchema(name="text", dtype=DataType.VARCHAR, 
                      max_length=self.text_processor.model.max_seq_length*5, enable_analyzer=True),
            FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR)
        ]

        # 配置混合搜索功能
        functions = [
            Function(
                name="text_bm25_emb",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25
            )
        ]

        # 创建并配置集合
        schema = CollectionSchema(fields, description="代码知识库", functions=functions)
        collection = Collection(self.config['collection_name'], schema)
        self._create_indexes(collection)
        return collection

    def _create_indexes(self, collection: Collection):
        """创建向量索引"""
        # 稠密向量索引
        collection.create_index(
            field_name="embedding",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "L2",
                "params": {"nlist": 128}
            }
        )
        
        # 稀疏向量索引
        collection.create_index(
            field_name="sparse",
            index_params={
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25"
            }
        )
        
        collection.load()
        print("[Milvus] 集合索引创建完成")

    def _load_knowledge_base(self):
        """加载知识库数据"""
        print("[Milvus] 开始加载知识库数据...")
        filenames, texts, embeddings = self.text_processor.process_directory(self.codebase_path)
        self.insert_data(filenames, texts, embeddings)
        print("[Milvus] 知识库数据加载完成")

    def insert_data(self, filenames: list, texts: list, embeddings: list):
        """插入数据到数据库"""
        entities = [
            {'filename': f, 'text': t, 'embedding': e}
            for f, t, e in zip(filenames, texts, embeddings)
        ]
        
        self.collection.insert(entities)
        self.collection.flush()
        print(f"[Milvus] 成功插入 {len(entities)} 条数据")

    def create_dense_search_request(self, query_text, top_k):
        _, embeddings = self.text_processor.chunk_text(query_text)
        return AnnSearchRequest(
            data=embeddings,
            anns_field="embedding",
            param=self.config["index_params"]["dense"]["search_params"],
            limit=top_k
        )

    def create_sparse_search_request(self, query_text, top_k):
        return AnnSearchRequest(
            data=[query_text],
            anns_field="sparse",
            param=self.config["index_params"]["sparse"]["search_params"],
            limit=top_k)
    def search(self, requests: List[AnnSearchRequest], top_k: int,reranker= None) -> List[Any]:
        """
        执行基础检索操作
        :param reranker: 
        :param requests: 检索请求列表
        :param top_k: 返回结果数量
        """
        search_results = self.collection.hybrid_search(
            reqs=requests,
            rerank=reranker,
            limit=top_k,
            output_fields=["filename", "text"]
        )
        return search_results
    
    async def async_search(self, requests: List[AnnSearchRequest], top_k: int, reranker= None) -> List[Any]:
        """
        执行基础检索操作
        :param reranker: 
        :param requests: 检索请求列表
        :param top_k: 返回结果数量
        """
        search_results = self.collection.hybrid_search(
            reqs=requests,
            rerank=reranker,
            limit=top_k,
            output_fields=["filename", "text"]
        )
        
        return search_results

    def _is_docker_running(self) -> bool:
        """检查Docker服务状态"""
        try:
            subprocess.run(
                self._DOCKER_CMD,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _start_docker(self):
        """启动Docker服务"""
        try:
            subprocess.run(["powershell.exe", "-Command", "docker desktop start"], check=True)
            print("[Docker] 服务已启动")
        except subprocess.CalledProcessError as e:
            print(f"[Error] Docker启动失败: {str(e)}")
            raise RuntimeError("Docker服务不可用") from e

if __name__ == "__main__":
    # 示例用法
    adapter = MilvusAdapter()
    sample_requests = [
        AnnSearchRequest(
            data=adapter.text_processor.model.encode("如何创建集合"),
            anns_field="embedding",
            param={"metric_type": "L2"},
            limit=3
        )
    ]
    results = adapter.search(sample_requests, top_k=3)
    
    for idx, hit in enumerate(results[0], 1):
        print(f"结果 {idx}:")
        print(f"文件: {hit.entity.get('filename')}")
        print(f"相似度: {hit.score:.4f}")
        print(f"内容: {hit.entity.get('text')}\n{'-'*50}")