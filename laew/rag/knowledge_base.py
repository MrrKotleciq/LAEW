"""Knowledge base loader for project memory and global knowledge."""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from laew.config.constants import RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP
from laew.rag.embedding import EmbeddingService
from laew.rag.obsidian import FRONTMATTER_RE, parse_note
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk, VectorStore


class KnowledgeScope(str, Enum):
    """Knowledge retrieval scope per ADR-011."""

    PROJECT = "project"
    GLOBAL = "global"
    HYBRID = "hybrid"


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    source: str
    file_path: str
    section_header: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    # Obsidian note metadata (Milestone 17). Preserved per chunk so that
    # frontmatter tags and [[backlinks]] survive chunking and are surfaced
    # in retrieved context. Empty when the source has no Obsidian metadata.
    tags: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)


class KnowledgeBase:
    """
    Manages knowledge loading from project memory and global knowledge sources.

    Handles document loading, chunking, embedding, and storage in vector store.
    """

    def __init__(
        self,
        project_root: str,
        knowledge_root: str,
        embedding_service: EmbeddingService,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
        vector_store_config: Optional[dict] = None,
    ):
        """
        Initialize knowledge base.

        Args:
            project_root: Root directory of the current project
            knowledge_root: Root directory of global knowledge vault
            embedding_service: Service for generating embeddings
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            vector_store_config: Optional configuration for persistent vector store.
                If provided and enabled, uses ChromaVectorStore; otherwise falls back
                to in-memory VectorStore.
        """
        self.project_root = Path(project_root)
        self.knowledge_root = Path(knowledge_root)
        self.embedding_service = embedding_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._vector_store_config = vector_store_config

        self._project_store = self._create_store("project")
        self._global_store = self._create_store("global")
        self._loaded = False
        # load_vault() indexes the global store on its own; it must not set
        # _loaded, or a later load() would skip reloading project memory.
        self._vault_loaded = False

    def _create_store(self, scope: str) -> VectorStore:
        """
        Create a vector store based on the configured backend.

        Args:
            scope: Scope name ("project" or "global")

        Returns:
            A ChromaVectorStore when a persistent store is enabled and reachable,
            otherwise an in-memory VectorStore.
        """
        config = self._vector_store_config or {}

        if config.get("enabled"):
            try:
                return ChromaVectorStore(
                    host=config.get("host", "localhost"),
                    port=int(config.get("port", 8000)),
                    collection_name=config.get(
                        f"{scope}_collection", f"laew_{scope}"
                    ),
                    source=scope,
                    timeout=int(config.get("timeout", 30)),
                )
            except (ConnectionError, ConnectionRefusedError, TimeoutError, ValueError) as e:
                # Graceful fallback to in-memory store when ChromaDB is unavailable
                # (includes import errors, connection errors, version mismatches, etc.).
                logger.debug("ChromaDB unavailable, falling back to in-memory store: %s", e)
                return VectorStore()

        return VectorStore()

    @staticmethod
    def _roots_overlap(a: Path, b: Path) -> bool:
        """
        Return True if two knowledge roots overlap.

        Two roots overlap when they are equal or one is nested inside the
        other. ``load``/``load_vault`` scan each root with ``rglob`` into its
        own store, so an overlap would index the same ``.md`` into both stores
        and duplicate it — exactly what ADR-011 forbids. Rejecting the overlap
        keeps ``@project`` and ``@knowledge`` as disjoint sibling directories.
        """
        a = Path(a).resolve()
        b = Path(b).resolve()
        return a == b or a.is_relative_to(b) or b.is_relative_to(a)

    def load(self, force: bool = False) -> None:
        """
        Load documents from project and global knowledge sources.

        Args:
            force: Force reload even if already loaded
        """
        if self._loaded and not force:
            return

        # Project and global knowledge must be disjoint sibling roots; otherwise
        # rglob over one root would reach the other and double-index the vault
        # into both stores, breaking the @project/@knowledge separation.
        if self._roots_overlap(self.project_root, self.knowledge_root):
            raise ValueError(
                "Project and knowledge roots overlap; configure them as "
                "disjoint sibling directories so @project and @knowledge stay "
                "separate."
            )

        # Load project memory
        if self.project_root.exists():
            self._load_directory(self.project_root, "project", self._project_store)

        # Load global knowledge
        if self.knowledge_root.exists():
            self._load_directory(self.knowledge_root, "global", self._global_store)

        self._loaded = True

    def load_vault(self, force: bool = False) -> None:
        """
        (Re)load only the global-knowledge Obsidian vault into its store.

        Unlike :meth:`load`, this does not touch project memory; it is used to
        (re)index the Second Brain vault on its own.

        Args:
            force: Force reload even if already loaded
        """
        if self._vault_loaded and not force:
            return

        # The vault must not overlap the project root, or rglob over the vault
        # root would reach project notes and double-index them into @knowledge.
        if self._roots_overlap(self.project_root, self.knowledge_root):
            raise ValueError(
                "Project and knowledge roots overlap; configure them as "
                "disjoint sibling directories so @project and @knowledge stay "
                "separate."
            )

        if self.knowledge_root.exists():
            self._load_directory(self.knowledge_root, "global", self._global_store)

        self._vault_loaded = True

    def structure(self) -> Dict[str, int]:
        """
        Inspect the Obsidian vault directory tree.

        Returns:
            Ordered dict mapping each immediate subfolder name to the number
            of ``.md`` notes it contains (0 for empty folders). Hidden folders
            and non-note directories are excluded.
        """
        counts: Dict[str, int] = {}

        if not self.knowledge_root.exists():
            return counts

        for folder in sorted(self.knowledge_root.iterdir()):
            if not folder.is_dir():
                continue
            if any(part.startswith(".") for part in folder.name.split(os.sep)):
                continue
            counts[folder.name] = sum(1 for _ in folder.rglob("*.md"))

        return counts

    def _load_directory(
        self,
        directory: Path,
        source: str,
        store: VectorStore,
    ) -> None:
        """
        Load all markdown files from a directory into a vector store.

        Args:
            directory: Directory to scan
            source: Source type ("project" or "global")
            store: Vector store to populate
        """
        chunks = []

        for md_file in directory.rglob("*.md"):
            # Skip hidden directories and common non-doc directories
            if any(
                part.startswith(".") or part in ("node_modules", "__pycache__", "venv")
                for part in md_file.relative_to(directory).parts
            ):
                continue

            file_chunks = self._load_file(md_file, source, directory)
            chunks.extend(file_chunks)

        if chunks:
            store.add_chunks(chunks)

    def _load_file(
        self,
        file_path: Path,
        source: str,
        base_dir: Path,
    ) -> List[DocumentChunk]:
        """
        Load and chunk a markdown file.

        Args:
            file_path: Path to the markdown file
            source: Source type ("project" or "global")
            base_dir: Base directory for relative path calculation

        Returns:
            List of DocumentChunks
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            return []

        # Extract Obsidian note metadata (tags, backlinks) once per file so it
        # is available for every chunk without re-parsing the frontmatter.
        obsidian_metadata = self._obsidian_metadata(content)

        # Strip frontmatter before section extraction so chunk text stays clean
        # of YAML and reflects only the note body.
        body = self._strip_frontmatter(content)
        sections = self._extract_sections(body)

        chunks = []
        for section_content, section_header in sections:
            # Chunk the section content
            section_chunks = self._chunk_text(section_content)

            for i, chunk_text in enumerate(section_chunks):
                # Generate embedding
                try:
                    embedding = self.embedding_service.embed(chunk_text)
                except (ValueError, RuntimeError) as e:
                    # Skip chunks that fail to embed (e.g., embedding model error)
                    logger.debug("Failed to embed chunk text: %s", e)
                    continue

                chunk_id = f"{source}:{file_path.relative_to(base_dir)}:{i}"
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    embedding=embedding,
                    source=source,
                    file_path=str(file_path.relative_to(base_dir)),
                    metadata={
                        "section_header": section_header,
                        "chunk_index": i,
                        **obsidian_metadata,
                    },
                )
                chunks.append(chunk)

        return chunks

    def _strip_frontmatter(self, content: str) -> str:
        """Remove a leading YAML frontmatter block from an Obsidian note."""
        match = FRONTMATTER_RE.search(content)
        return content[match.end():] if match else content

    def _obsidian_metadata(self, content: str) -> Dict[str, List[str]]:
        """
        Extract Obsidian note metadata for RAG indexing.

        Args:
            content: Note text (frontmatter + body).

        Returns:
            Dict with ``tags`` and ``backlinks`` lists (empty when absent).
        """
        note = parse_note(content)
        return {
            "tags": list(note["tags"]),
            "backlinks": list(note["backlinks"]),
        }

    def _extract_sections(self, content: str) -> List[tuple[str, str]]:
        """
        Extract sections from markdown content based on headers.

        Args:
            content: Markdown content

        Returns:
            List of (section_content, header_text) tuples
        """
        # Split by markdown headers
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(header_pattern.finditer(content))

        if not matches:
            return [(content, "")]

        sections = []

        # Add content before first header as preamble
        if matches[0].start() > 0:
            preamble = content[: matches[0].start()].strip()
            if preamble:
                sections.append((preamble, ""))

        for i, match in enumerate(matches):
            # Get section content (from this header to next header)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)

            section_content = content[start:end].strip()
            header_text = match.group(2).strip()

            if section_content:
                sections.append((section_content, header_text))

        return sections

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at a sentence or paragraph boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for sep in [". ", ".\n", "? ", "! "]:
                        sent_break = text.rfind(sep, start, end)
                        if sent_break > start + self.chunk_size // 2:
                            end = sent_break + len(sep)
                            break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    @property
    def project_store(self) -> VectorStore:
        """Get the project knowledge vector store."""
        return self._project_store

    @property
    def global_store(self) -> VectorStore:
        """Get the global knowledge vector store."""
        return self._global_store

    def get_store(self, scope: KnowledgeScope) -> VectorStore:
        """
        Get vector store for a specific scope.

        Args:
            scope: Knowledge scope

        Returns:
            VectorStore for the scope
        """
        if scope == KnowledgeScope.PROJECT:
            return self._project_store
        elif scope == KnowledgeScope.GLOBAL:
            return self._global_store
        else:
            # For hybrid, we search both stores
            return self._project_store

    def count_chunks(self, scope: Optional[KnowledgeScope] = None) -> int:
        """
        Count total chunks loaded.

        Args:
            scope: Optional scope filter

        Returns:
            Number of chunks
        """
        if scope is None:
            return self._project_store.count() + self._global_store.count()
        elif scope == KnowledgeScope.PROJECT:
            return self._project_store.count()
        elif scope == KnowledgeScope.GLOBAL:
            return self._global_store.count()
        return 0
