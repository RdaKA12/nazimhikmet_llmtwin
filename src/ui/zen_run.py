from src.zen.pipelines.crawl_pipeline import crawl_pipeline


if __name__ == "__main__":
    pipeline = crawl_pipeline()
    try:
        pipeline.run()
    except AttributeError as exc:
        # Work around a known ZenML bug where PipelineRunResponse.run is missing.
        if "PipelineRunResponse" not in str(exc):
            raise
    print("ZenML crawl pipeline finished.")
