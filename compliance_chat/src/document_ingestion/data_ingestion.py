from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from compliance_chat.utils.model_loader import ModelLoader
from compliance_chat.logger import GLOBAL_LOGGER as log
from compliance_chat.exception.custom_exception import DocumentPortalException
import json
import uuid
from datetime import datetime
from compliance_chat.utils.file_io import save_uploaded_files
from compliance_chat.utils.document_ops import load_documents
import hashlib
import sys


def generate_session_id() -> str:
    """Generate a unique session ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"session_{timestamp}_{unique_id}"


class ChatIngestor:
    def __init__(
        self,
        temp_base: str = "data",
        use_session_dirs: bool = True,
        session_id: Optional[str] = None,
    ):
        try:
            self.model_loader = ModelLoader()

            self.use_session = use_session_dirs
            self.session_id = session_id or generate_session_id()

            self.temp_base = Path(temp_base)
            self.temp_base.mkdir(parents=True, exist_ok=True)

            self.temp_dir = self._resolve_dir(self.temp_base)

            # Pinecone index name based on session
            self.index_name = self.model_loader.get_pinecone_index_name()
            self.namespace = self.session_id if self.use_session else "default"

            log.info(
                "ChatIngestor initialized",
                session_id=self.session_id,
                temp_dir=str(self.temp_dir),
                index_name=self.index_name,
                namespace=self.namespace,
                sessionized=self.use_session,
            )
        except Exception as e:
            log.error("Failed to initialize ChatIngestor", error=str(e))
            raise DocumentPortalException("Initialization error in ChatIngestor", e) from e

    def _resolve_dir(self, base: Path):
        if self.use_session:
            d = base / self.session_id
            d.mkdir(parents=True, exist_ok=True)
            return d
        return base

    def _split(
        self, docs: List[Document], chunk_size=1000, chunk_overlap=200
    ) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        chunks = splitter.split_documents(docs)
        log.info(
            "Documents split",
            chunks=len(chunks),
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )
        return chunks

    def built_retriver(
        self,
        uploaded_files: Iterable,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        k: int = 5,
        search_type: str = "mmr",
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
    ):
        try:
            paths = save_uploaded_files(uploaded_files, self.temp_dir)
            docs = load_documents(paths)
            if not docs:
                raise ValueError("No valid documents loaded")

            chunks = self._split(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            # Get embeddings
            embeddings = self.model_loader.load_embeddings()

            # Create/update Pinecone vector store
            vectorstore = PineconeVectorStore.from_documents(
                documents=chunks,
                embedding=embeddings,
                index_name=self.index_name,
                namespace=self.namespace,
            )

            log.info(
                "Pinecone index updated",
                chunks=len(chunks),
                index_name=self.index_name,
                namespace=self.namespace,
            )

            # Configure search parameters based on search type
            search_kwargs = {"k": k}

            if search_type == "mmr":
                # MMR needs fetch_k (docs to fetch) and lambda_mult (diversity parameter)
                search_kwargs["fetch_k"] = fetch_k
                search_kwargs["lambda_mult"] = lambda_mult
                log.info("Using MMR search", k=k, fetch_k=fetch_k, lambda_mult=lambda_mult)

            return vectorstore.as_retriever(
                search_type=search_type, search_kwargs=search_kwargs
            )

        except Exception as e:
            log.error("Failed to build retriever", error=str(e))
            raise DocumentPortalException("Failed to build retriever", e) from e


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
