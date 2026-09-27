# Voiceprint, tutor and review export

## Voiceprint
Uses sherpa-onnx SpeakerEmbeddingExtractor and the official 3D-Speaker ERes2Net base model. Source: https://k2-fsa.github.io/sherpa/onnx/speaker-identification/index.html
After a successful complete download, create models/voiceprint/3dspeaker.ready. Incomplete downloads are not loaded.
Model: models/voiceprint/3dspeaker.onnx, override with BEYOND_WORDS_VOICEPRINT_MODEL.
Enrollment requires explicit consent and manually confirmed speech with at least 8 seconds of non-overlapping audio. Embeddings stay on the application backend and are scoped to the authenticated user. No biometric inference, authentication, or third-party audio upload occurs. Profile provides deletion, and account/data deletion clears the embedding.
Matching requires at least 4 seconds per speaker, cosine similarity >= 0.75 and a margin >= 0.15. These conservative starting thresholds have NOT been calibrated on user recordings; matching can be wrong and manual correction remains available. Existing recordings return a candidate for confirmation; new transcription runs can mark a qualifying match automatically. Unknown, short, or unavailable matches stay unconfirmed. Multilingual and cross-microphone accuracy needs real-world evaluation.

## Tutor
Session-scoped chat history is saved server-side. DeepSeek receives redacted transcript context and the last 20 chat messages. Modes support roleplay or language explanation. Voice replies use existing Qwen transcription with explicit consent; playback uses existing Qwen TTS. Delete AI content also deletes tutor history. A maximum of 100 exchanges per recording bounds context growth.

## Export
GET /api/v1/sessions/{id}/export.docx requires the session owner. Outputs A4 Word documents with headings, language-learning points, transcript timestamps and page numbers. Incomplete reviews are marked rather than fabricated. Layout has not been visually verified in Word.

## Setup
Install backend/requirements.txt. Run Alembic migrations through 20260927_0010 in production. Development auto-schema creates tutor_conversations and adds voiceprint_json without deleting existing data.
