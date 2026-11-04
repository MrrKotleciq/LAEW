"""Composition and lifecycle for review-only Global Knowledge curation."""
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger(__name__)


def build_knowledge(manifest, conversations, *, projects_root,
                    knowledge_root, broker_factory, sync_callback, discovery_base=None):
    from laew.security.path_resolver import PathResolver
    from laew.tools.filesystem import FilesystemTool
    from .service import KnowledgeCurationService
    from laew.rag.config import manifest_global_exclusions, resolve_knowledge_root
    from laew.rag.knowledge_base import KnowledgeScope
    from laew.rag.pipeline import RAGPipeline
    path = (Path(os.environ['LAEW_KNOWLEDGE_STORAGE']) if os.environ.get('LAEW_KNOWLEDGE_STORAGE')
            else conversations.directory.parent / 'knowledge' / 'curation.db')
    filesystem = FilesystemTool(PathResolver(projects_root=projects_root,
        knowledge_root=knowledge_root, general=True))
    index_root = resolve_knowledge_root(manifest, project_root=None,
        projects_root=projects_root, knowledge_root=knowledge_root)

    def discover(title):
        if discovery_base is None:
            return []
        try:
            kb = discovery_base()
            if kb is None:
                return []
            pipeline = RAGPipeline(kb, kb.embedding_service)
            pipeline.require_freshness = True
            result = pipeline.retrieve(title, scope=KnowledgeScope.GLOBAL, top_k=5)
            return ['@knowledge/' + (kb.knowledge_root / chunk.file_path)
                .relative_to(filesystem.resolver.knowledge_root).as_posix() for chunk, _ in result.chunks]
        except Exception as exc:
            log.debug('Semantic proposal discovery unavailable (%s)', type(exc).__name__)
            return []

    service = KnowledgeCurationService(path, conversations, filesystem,
        broker_factory, sync_callback, exclusions=manifest_global_exclusions(manifest),
        discovery_callback=discover, index_root=index_root)
    return service


class KnowledgeWorker:
    """One bounded worker; jobs and index retry state remain in SQLite."""

    def __init__(self, service, conversations, provider_factory):
        self.service = service
        self.conversations = conversations
        self.provider_factory = provider_factory
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._guard = threading.Lock()
        self.thread = None

    def start(self):
        with self._guard:
            if self.thread is not None:
                return
            self.thread = threading.Thread(target=self._run, name='laew-knowledge', daemon=True)
            self.thread.start()

    def request(self):
        self.start()
        self._wake.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.service.sync_index()
                self.service.process_extraction(self.conversations, self.provider_factory)
            except Exception:
                log.exception('Knowledge background operation failed')
            self._wake.wait(60)
            self._wake.clear()

    def close(self):
        self._stop.set()
        self._wake.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
