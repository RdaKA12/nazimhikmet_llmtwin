from src.zen.pipeline import crawl_embed_pipeline

if __name__ == "__main__":
    # run the pipeline once; ZenML server & stack are provided via env/config
    pipeline = crawl_embed_pipeline()
    try:
        pipeline.run()
    except AttributeError as exc:
        # Work around a known ZenML quirk where PipelineRunResponse.run may be missing
        if "PipelineRunResponse" not in str(exc):
            raise
