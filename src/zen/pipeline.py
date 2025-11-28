"""Expose ZenML pipelines for easy imports."""

from src.zen.pipelines.crawl_pipeline import crawl_pipeline as crawl_embed_pipeline

__all__ = ["crawl_embed_pipeline"]
