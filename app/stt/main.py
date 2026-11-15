from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from faster_whisper import WhisperModel
import tempfile, os

model_name = "deepdml/faster-whisper-large-v3-turbo-ct2"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = getattr(app.state, "model", None)
    if app.state.model is None:
        app.state.model = WhisperModel(model_name)
    yield


app = FastAPI(
    # 各種デバッグ用 URL を無効化する
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


def get_model():
    model = getattr(app.state, "model", None)
    if model is None:
        model = WhisperModel(model_name)
        app.state.model = model
    return model


# OpenAI API 互換の文字起こしエンドポイント
@app.post("/v1/audio/transcriptions")
async def audio_transcription(file: UploadFile = File(...), language: str = "ja"):
    if file.filename is None:
        raise HTTPException(status_code=400, detail="A file name is required.")

    model = get_model()
    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
        segments, _ = model.transcribe(
            tmp_path,
            language=language,
            vad_filter=True,   # 無音区間を切る
            beam_size=1,       # 速度優先
            temperature=0.0,
        )
        text = "".join(seg.text for seg in segments).strip()
    return {"text": text}
