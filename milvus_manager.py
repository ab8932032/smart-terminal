import os
import re
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility, Function, FunctionType, AnnSearchRequest, RRFRanker
from sentence_transformers import SentenceTransformer
import subprocess

class MilvusManager:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name, local_files_only=True)
        self.collection = None
        os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'
        
        self.start_milvus_service()
        self.initialize_milvus()

        # 假设你的代码库路径是'/path/to/codebase'
        codebase_path = '.\\'

        # 处理目录并插入数据到Milvus
        filenames, texts, embeddings = self.process_directory(codebase_path)
        self.insert_data_to_milvus(filenames, texts, embeddings)

    def start_milvus_service(self):
        try:
            # 使用Docker命令启动已有的Milvus容器
            subprocess.run(["powershell.exe", "-Command", "docker desktop start"], check=True, shell=True)
            subprocess.run(["powershell.exe", "-Command", ".\\standalone.bat start"], check=True, shell=True)
            connections.connect("default", host="localhost", port="19530")
            print("Milvus容器已启动")
        except subprocess.CalledProcessError as e:
            print(f"启动Milvus容器失败: {e}")

    def initialize_milvus(self):
        if utility.has_collection("codebase_kb"):
            utility.drop_collection("codebase_kb")

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=1024, enable_analyzer=True),
            FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR)
        ]
        functions = [
            Function(
                name="text_bm25_emb",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
        ]
        schema = CollectionSchema(fields, "", functions)
        self.collection = Collection(name="codebase_kb", schema=schema)

        index_params = {
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128, "m": 8},
            "metric_type": "L2"
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)

        index_params = {
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "BM25"
        }
        self.collection.create_index(field_name="sparse", index_params=index_params)

        self.collection.load()
        
        server_version = utility.get_server_version()
        print(f"Milvus Server Version: {server_version}")

    def chunk_text(self, text, max_length=512, text_length=1024):
        """
        将文本分割成不超过max_length个token的块，并保留10%的上下文token。
        :param text: 要分割的原始文本。
        :param max_length: 每个块的最大token数。
        :param text_length: 总文本的最大长度。
        :return: 包含文本块的列表、嵌入向量列表和稀疏嵌入向量列表。
        """
        tokens = self.model.tokenizer.tokenize(text)
        chunks = []
        embeddings = []
        current_chunk = []
        overlap_length = max_length // 10  # 10% overlap
        total_length = 0
        for token in tokens:
            total_length += len(token.encode('utf-8'))
            if total_length > text_length:
                chunk = ''.join(current_chunk).strip()
                chunks.append(chunk)
                embeddings.append(self.model.encode(chunk))
                # 保留后半部分作为下一个chunk的开始
                current_chunk = current_chunk[max_length - overlap_length:]
                total_length = len(''.join(current_chunk).strip().encode('utf-8'))
            else:
                current_chunk.append(token)
                if len(current_chunk) >= max_length - 2:
                    chunk = ''.join(current_chunk).strip()
                    chunks.append(chunk)
                    embeddings.append(self.model.encode(chunk))
                    # 保留后半部分作为下一个chunk的开始
                    current_chunk = current_chunk[max_length - overlap_length:]
                    total_length = len(''.join(current_chunk).strip().encode('utf-8'))
        
        # 添加最后一个chunk
        if current_chunk:
            chunk = ''.join(current_chunk).strip()
            chunks.append(chunk)
            embeddings.append(self.model.encode(chunk))
        
        return chunks, embeddings

    def _clean_code(self, code, file_extension):
        """
        清洗代码内容，去除注释和空行。
        :param code: 原始代码字符串。
        :param file_extension: 文件扩展名（如 '.py', '.cpp', '.ts'）。
        :return: 清洗后的代码字符串。
        """
        if file_extension in ['.py']:
            # 去除Python单行注释
            code = re.sub(r'#.*', '', code)
            # 去除Python多行注释
            code = re.sub(r'\'\'\'(.*?)\'\'\'', '', code, flags=re.DOTALL)
            code = re.sub(r'\"\"\"(.*?)\"\"\"', '', code, flags=re.DOTALL)
        elif file_extension in ['.cpp', '.ts', '.js']:
            # 去除C++/TypeScript/JavaScript单行注释
            code = re.sub(r'//.*', '', code)
            # 去除C++/TypeScript/JavaScript多行注释
            code = re.sub(r'/\*(.*?)\*/', '', code, flags=re.DOTALL)
        
        # 去除空行
        code = re.sub(r'\n\s*\n', '\n', code)
        # 去除多余空格
        code = re.sub(r'\s+', ' ', code)
        return code.strip()


    def process_directory(self, directory):
        filenames = []
        texts = []
        embeddings = []
        for root, _, files in os.walk(directory):
            for file in files:
                file_extension = os.path.splitext(file)[1].lower()
                if file_extension =='.py':  # 假设只处理Python文件
                    file_path = os.path.abspath(os.path.join(root, file))  # 使用绝对路径
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    chunks, chunk_embeddings = self.chunk_text(self._clean_code(content,file_extension))
                    filenames.extend([file_path] * len(chunks))
                    texts.extend(chunks)
                    embeddings.extend(chunk_embeddings)
        return filenames, texts, embeddings

    def insert_data_to_milvus(self, filenames, texts, embeddings):
        
        print(f"insert start!!!")
        entities = []
        for i in range(len(embeddings)):
            entities.append({'filename': filenames[i], 'embedding': embeddings[i], 'text': texts[i]})
            # 打印filename和text的长度
        self.collection.insert(entities)  # 使用MilvusClient的insert方法
        self.collection.flush()
        print(f"insert finish!!!")

    def search_in_milvus(self, query, top_k=5):
        chunks, chunk_embeddings = self.chunk_text(query)
        request1 = AnnSearchRequest(
            data=chunk_embeddings,
            anns_field="embedding",
            param={"metric_type": "L2", "params": {"nprobe": 32}},
            limit=top_k
        )  # 使用Collection的search方法

        request2 = AnnSearchRequest(
            data=chunks,
            anns_field="sparse",
            param={'params': {'drop_ratio_search': 0.1}},
            limit=top_k
        )  # 使用Collection的search方法
        
        reqs = [request1, request2]
        res = self.collection.hybrid_search(reqs, RRFRanker(60), top_k, output_fields=["filename","text"])#, group_by_field="filename")
        listRes = []
        for hits in res:
            for hit in hits:
                listRes.append({"score": hit.score, "entity": hit.fields})

        return listRes