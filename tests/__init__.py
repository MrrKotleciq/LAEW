"""LAEW test suite package.

Marks the ``tests`` tree as a package so that cross-test-module imports such
as ``from tests.unit.test_rag import MockEmbeddingService`` resolve under both
console-script ``pytest`` and ``python -m pytest`` invocation. With these
package markers present, pytest's prepend import mode inserts the repository
root on ``sys.path`` for ``tests.unit.*`` modules.
"""