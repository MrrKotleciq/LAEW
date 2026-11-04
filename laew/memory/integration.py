"""Shared memory composition and one bounded, lifecycle-managed worker."""
import hashlib
import logging
import os
import threading
from pathlib import Path
from .store import MemoryStore
from .service import MemoryService

log = logging.getLogger(__name__)


def build_memory(manifest, manifest_path):
    from laew.console.session_store import conversation_store_from_manifest
    from laew.runtime import build_embedding_service
    from laew.rag.vector_store import ChromaVectorStore
    from laew.rag.embedding import embedding_model_identity
    sessions=conversation_store_from_manifest(manifest, manifest_path)
    path=Path(os.environ['LAEW_MEMORY_STORAGE']) if os.environ.get('LAEW_MEMORY_STORAGE') else sessions.directory.parent/'memory'/'memory.db'
    store=MemoryStore(path)
    embedding=None
    def embed():
        nonlocal embedding
        if embedding is None:
            embedding=build_embedding_service(manifest)
            if hasattr(embedding,'timeout'): embedding.timeout=min(embedding.timeout,3)
        return embedding
    config=manifest.get('rag',{}).get('vector_store',{})
    collection_name=('laew_ltm_'+hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]) if os.environ.get('LAEW_MEMORY_STORAGE') else 'laew_long_term_memory'
    def index():
        if not config.get('enabled'): raise RuntimeError('ChromaDB is disabled in the manifest.')
        return ChromaVectorStore(host=config.get('host','localhost'),port=int(config.get('port',8000)),
            timeout=min(int(config.get('timeout',30)),5),collection_name=collection_name,source='memory',
            embedding_model_id=embedding_model_identity(embed()))
    def reset_index():
        import chromadb
        from laew.rag.vector_store import _build_chroma_client
        if not config.get('enabled'): raise RuntimeError('ChromaDB is disabled in the manifest.')
        client=_build_chroma_client(chromadb,config.get('host','localhost'),int(config.get('port',8000)),5)
        try: client.delete_collection(collection_name)
        except chromadb.errors.NotFoundError: pass
        return index()
    return MemoryService(store,index_factory=index,embedding_factory=embed,reset_index_factory=reset_index)


def extraction_provider(manifest, selection, cloud=None):
    from laew.runtime import build_provider_for_role
    from laew.llm.registry import create_provider
    provider=selection.get('provider'); model=selection.get('model')
    if not model or not provider: raise ValueError('Choose an extraction model or use an active chat model.')
    if provider in ('gemini','openai-api','chatgpt'):
        if cloud is None:
            from laew.cloud_chat import CloudChatService
            cloud=CloudChatService()
        return cloud.provider(provider,selection.get('account_id')),model
    if provider=='manifest': return build_provider_for_role(manifest,'primary'),model
    configs=manifest.get('agent',{}).get('llm',{}).get('providers',[])
    config=next((x for x in configs if x.get('type')==provider),{'type':provider})
    return create_provider(config),model


class MemoryWorker:
    def __init__(self, service, conversations, provider_factory):
        self.service=service; self.conversations=conversations; self.provider_factory=provider_factory
        self.stop_event=threading.Event(); self.wake_event=threading.Event(); self.thread=None
        self.rebuild=False; self._guard=threading.Lock()

    def start(self):
        with self._guard:
            if self.thread is not None: return
            self.thread=threading.Thread(target=self._run,name='laew-memory',daemon=True)
            self.thread.start()

    def request(self, rebuild=False):
        with self._guard: self.rebuild=self.rebuild or rebuild
        self.start(); self.wake_event.set()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                with self._guard: rebuild=self.rebuild; self.rebuild=False
                with self.service.store.connection() as db:
                    pending=db.execute('SELECT 1 FROM memory_index_outbox WHERE completed_at IS NULL LIMIT 1').fetchone()
                if pending or rebuild: self.service.sync_index(rebuild=rebuild)
                self.service.process_extraction(self.conversations,self.provider_factory)
            except Exception:
                log.exception('Memory background operation failed')
            self.wake_event.wait(60); self.wake_event.clear()

    def close(self):
        self.stop_event.set(); self.wake_event.set()
        if self.thread: self.thread.join(timeout=5)
