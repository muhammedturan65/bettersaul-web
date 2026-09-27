"""BetterSaul Source Connector package."""
from .connectors import (
    BaseConnector, LegalDocument, SearchResponse, RateLimiter, RateLimitError,
    YargitayConnector, DanistayConnector, EmsalConnector,
    AnayasaConnector, ResmiGazeteConnector, MevzuatConnector,
    CONNECTORS, get_connector,
)
from .embeddings import (
    EmbeddingBackend, TfidfHashBackend, SentenceTransformersBackend,
    OpenAIEmbeddingBackend, get_embedding_backend, chunk_text,
)
from .db_writer import DatabaseWriter
from .worker import ImportWorker, ImportProgress, JobManager

__version__ = "1.0.0"
