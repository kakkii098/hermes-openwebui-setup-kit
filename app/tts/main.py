from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool

import io
import os
import soundfile
import librosa
import torch
import hashlib
from faster_qwen3_tts import FasterQwen3TTS

def get_prompt_hash(audio_path, text_path: str) -> str:
    """
    参照音声とテキストのハッシュ値を計算する関数
    """

    # 音声ファイルのハッシュを計算
    with open(audio_path, "rb") as f:
        audio_hash = hashlib.sha256(f.read()).hexdigest()

    # テキストファイルのハッシュを計算
    with open(text_path, "rb") as f:
        text_hash = hashlib.sha256(f.read()).hexdigest()

    # 音声とテキストのハッシュを組み合わせて返す
    combined_hash = hashlib.sha256((audio_hash + text_hash).encode()).hexdigest()
    return combined_hash

def load_voice_clone_prompt(model, audio_path: str, text_path: str, hash_path: str, prompt_path: str):
    # 前回のモデルのハッシュ値を取得
    if os.path.exists(hash_path):
        with open(hash_path, "r") as f:
            previous_hash = f.read().strip()
    else:
        previous_hash = None
    
    # 現在の参照音声とテキストのハッシュ値を計算
    current_hash = get_prompt_hash(audio_path, text_path)

    # ハッシュ値が異なる場合、または前回のハッシュが存在しない場合に再生成
    if current_hash != previous_hash:
        # 音声をロード
        wav, sr = librosa.load(audio_path, sr=24000, mono=True)

        # 参照テキストをロード
        with open(text_path, "r", encoding="utf-8") as f:
            reference_text = f.read().strip()

        # 参照音声とテキストから Voice Clone 用プロンプトを抽出（プリビルド）
        voice_clone_prompt = model.model.create_voice_clone_prompt(
            ref_audio=(wav, sr),
            ref_text=reference_text,
        )
        # prompt とハッシュ値を保存
        torch.save(voice_clone_prompt, prompt_path)
        with open(hash_path, "w") as f:
            f.write(current_hash)
    else:
        # 前回のハッシュ値が同じ場合、既存のプロンプトをロード
        voice_clone_prompt = torch.load(prompt_path)

    return voice_clone_prompt

def split_text_into_chunks(text: str, delimiters: list) -> list[str]:
    for d in delimiters:
        text = text.replace(d, f"{d}<SPLIT>")
    chunks = [chunk.strip() for chunk in text.split("<SPLIT>") if chunk.strip()]
    return chunks if chunks else [text]

@asynccontextmanager
async def lifespan(app: FastAPI):
    reference_audio_path = "/resources/reference_audio.wav"
    reference_text_path = "/resources/reference_text.txt"
    reference_hash_path = "/resources/reference_hash.txt"
    reference_prompt_path = "/resources/voice_clone_prompt.pt"

    # FastAPI 起動時にモデルを初期化
    model = FasterQwen3TTS.from_pretrained("Qwen/Qwen3-TTS-12Hz-0.6B-Base")

    # 参照音声とテキストから Voice Clone 用プロンプトをロードまたは生成
    voice_clone_prompt = load_voice_clone_prompt(
        model=model,
        audio_path=reference_audio_path,
        text_path=reference_text_path,
        hash_path=reference_hash_path,
        prompt_path=reference_prompt_path,
    )

    app.state.model = model
    app.state.voice_clone_prompt = voice_clone_prompt

    yield

app = FastAPI(
    # 各種デバッグ用 URL を無効化する
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    # FastAPI の起動時と終了時に実行する処理を定義
    lifespan=lifespan,
)

# OpenAI API 互換のTTSエンドポイント(input 以外のキーワードは未使用)
@app.post("/audio/speech")
async def audio_transcription(request: Request):
    model = get_model(request=request)
    voice_clone_prompt = get_voice_clone_prompt(request=request)
    if not model or voice_clone_prompt is None:
        raise HTTPException(status_code=500, detail={"error": "Model not initialized."})
  
    body = await request.json()
    text = body.get("input")

    def _generate():
        return model.generate_voice_clone(
            text=text,
            language="Japanese",
            voice_clone_prompt=voice_clone_prompt,
        )
    wavs, sr = await run_in_threadpool(_generate)
    
    # バイトストリーム（WAV形式）として返却
    buffer = io.BytesIO()
    soundfile.write(buffer, wavs[0], sr, format="WAV")
    buffer.flush()
    buffer.seek(0)

    return Response(content=buffer.read(), media_type="audio/wav")

def get_model(request: Request):
    return request.app.state.model

def get_voice_clone_prompt(request: Request):
    return request.app.state.voice_clone_prompt
