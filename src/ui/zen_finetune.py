from src.zen.pipelines.finetune_pipeline import finetune_pipeline


if __name__ == "__main__":
    pipeline = finetune_pipeline()
    try:
        pipeline.run()
    except AttributeError as exc:
        # Work around a known ZenML bug where PipelineRunResponse.run is missing.
        if "PipelineRunResponse" not in str(exc):
            raise
    print("ZenML fine-tune pipeline finished.")

