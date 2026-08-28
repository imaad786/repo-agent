import torch
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

from src import settings


def get_embedding_model() -> Embeddings:
    device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"
    model_kwargs = {"device": device}
    encode_kwargs = {"normalize_embeddings": True}
    return HuggingFaceEmbeddings(
        model_name=settings.hugging_face_embedding_model_id,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
    )
