from .asr import asr_status, load_model
from .diarization import diarization_status, load_pipeline


def main() -> None:
    print("Preparing ASR model...")
    load_model()
    print(asr_status())
    status = diarization_status()
    if not status["available"]:
        raise SystemExit(
            "Speaker diarization is not configured. Accept the Community-1 model terms "
            "and set HF_TOKEN before running setup again."
        )
    print("Preparing speaker diarization model...")
    load_pipeline()
    print(diarization_status())
    print("Speech models are ready.")


if __name__ == "__main__":
    main()

