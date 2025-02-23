from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
from typing import Tuple
import os

class TextProcessor:
    def __init__(self, model):
        """
        文本处理工具类
        :param model_max_length: 模型最大序列长度，默认512
        """
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=model.max_seq_length,
            chunk_overlap=int(model.max_seq_length * 0.1),
            length_function=lambda x: len(model.tokenizer.tokenize(x)),
            separators=['\n\n```', '\n\n', '\n', ' ', '']
        )
        self.model = model
    
    def clean_code(self, code: str, file_extension: str) -> str:
        """代码清洗标准化方法"""
        # 语言特定规则
        if file_extension == '.py':
            code = re.sub(r'#.*', '', code)
            code = re.sub(r'\'\'\'(.*?)\'\'\'', '', code, flags=re.DOTALL)
            code = re.sub(r'\"\"\"(.*?)\"\"\"', '', code, flags=re.DOTALL)
        elif file_extension in ('.cpp', '.ts', '.js'):
            code = re.sub(r'//.*', '', code)
            code = re.sub(r'/\*(.*?)\*/', '', code, flags=re.DOTALL)
        
        # 通用处理规则
        code = re.sub(r'\n{3,}', '\n\n', code)  # 压缩多空行
        code = re.sub(r'(?<=\n)\s+', ' ', code)  # 保留缩进空格
        return code.strip()

    def chunk_text(self, text: str,file_extension: str):
        """
        文本分块处理
        :return: (文本块列表, 嵌入向量列表)
        """
        chunks = self.text_splitter.split_text(self.clean_code(text,file_extension))
        
        return chunks, [self.model.encode(chunk) for chunk in chunks]
    
    
    def process_directory(self, directory: str) -> tuple:
        """处理目录中的代码文件"""
        filenames, texts, embeddings = [], [], []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                chunks, chunk_embeddings = self.chunk_text(content, '.py')
                
                filenames.extend([file_path] * len(chunks))
                texts.extend(chunks)
                embeddings.extend(chunk_embeddings)
        
        return filenames, texts, embeddings