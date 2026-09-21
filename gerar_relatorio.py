"""
Gera o relatório de contatos que pediram falar com vendedor/atendente/humano/comercial,
filtrando por Hunter = "digital", a partir da API do Weni Flows.

Equivalente ao Power Query que estava rodando no Excel, mas:
  - roda fora do Excel (GitHub Actions), então não trava a planilha;
  - mantém um cache local de mensagens e contatos já buscados, e em cada
    execução só busca o que é NOVO desde a última vez (usando os campos
    created_on / modified_on da API), em vez de rebaixar tudo de novo.

O token da API vem da variável de ambiente WENI_API_TOKEN (configurada como
Secret no GitHub, nunca escrita neste arquivo).
"""

import json
import os
from pathlib import Path

import pandas as pd
import requests

# ============================================================
# CONFIGURAÇÃO
# ============================================================
API_BASE_URL = "https://flows.weni.ai"
API_TOKEN = os.environ["WENI_API_TOKEN"]

DATA_INICIO = "2026-06-14T00:00:00Z"  # não busca mensagens de antes disso

PALAVRAS_ALVO = ["vendedor", "atendente", "humano", "comercial"]
VALOR_HUNTER_ALVO = "digital"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
MESSAGES_CACHE_PATH = DATA_DIR / "messages_cache.json"
CONTACTS_CACHE_PATH = DATA_DIR / "contacts_cache.json"
OUTPUT_PATH = OUTPUT_DIR / "relatorio.xlsx"

HEADERS = {"Authorization": f"Token {API_TOKEN}"}


# ============================================================
# BUSCA NA API (segue a paginação "next")
# ============================================================
def buscar_tudo(endpoint_relativo):
    session = requests.Session()
    session.headers.update(HEADERS)
    url = API_BASE_URL + endpoint_relativo
    resultados = []
    while url:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        resultados.extend(payload.get("results", []))
        url = payload.get("next")
    return resultados


# ============================================================
# CACHE EM DISCO (fica na pasta data/, restaurado via actions/cache
# entre execuções — não é commitado no histórico do git, por conter
# dados de contatos)
# ============================================================
def carregar_cache(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_cache(path, dados):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def atualizar_mensagens():
    cache = carregar_cache(MESSAGES_CACHE_PATH)  # id (str) -> registro

    if cache:
        maior_data = max(m["created_on"] for m in cache.values())
        endpoint = f"/api/v2/messages.json?folder=incoming&after={maior_data}"
    else:
        endpoint = f"/api/v2/messages.json?folder=incoming&after={DATA_INICIO}"

    novas = buscar_tudo(endpoint)
    for msg in novas:
        cache[str(msg["id"])] = msg

    salvar_cache(MESSAGES_CACHE_PATH, cache)
    print(f"Mensagens: {len(novas)} novas buscadas, {len(cache)} no total no cache.")
    return list(cache.values())


def atualizar_contatos():
    cache = carregar_cache(CONTACTS_CACHE_PATH)  # uuid -> registro

    if cache:
        maior_data = max(c["modified_on"] for c in cache.values())
        endpoint = f"/api/v2/contacts.json?after={maior_data}"
    else:
        endpoint = "/api/v2/contacts.json"  # primeira execução: busca tudo

    novos = buscar_tudo(endpoint)
    for c in novos:
        cache[c["uuid"]] = c

    salvar_cache(CONTACTS_CACHE_PATH, cache)
    print(f"Contatos: {len(novos)} novos/atualizados buscados, {len(cache)} no total no cache.")
    return list(cache.values())


# ============================================================
# MESMA LÓGICA DA CONSULTA ORIGINAL EM POWER QUERY
# ============================================================
def normalizar(texto):
    partes = [p for p in (texto or "").lower().split(" ") if p != ""]
    return " ".join(partes)


def bateu(msg_norm):
    return "falar com" in msg_norm and any(p in msg_norm for p in PALAVRAS_ALVO)


def montar_relatorio(mensagens, contatos):
    df_msg = pd.DataFrame(mensagens)
    df_msg["ContatoUUID"] = df_msg["contact"].apply(lambda c: c.get("uuid") if isinstance(c, dict) else None)
    df_msg["Nome"] = df_msg["contact"].apply(lambda c: c.get("name") if isinstance(c, dict) else None)
    df_msg = df_msg[["ContatoUUID", "Nome", "text", "created_on"]].copy()

    df_msg["MsgNorm"] = df_msg["text"].apply(normalizar)
    df_msg["Bateu"] = df_msg["MsgNorm"].apply(bateu)

    so_bateu = df_msg[df_msg["Bateu"]].copy()
    so_bateu = so_bateu.sort_values(["ContatoUUID", "created_on"])

    # primeira vez que cada contato bateu com a frase
    primeira = so_bateu.groupby("ContatoUUID", as_index=False).first()

    # quantas vezes cada contato bateu, no total
    contagem = (
        so_bateu.groupby("ContatoUUID", as_index=False)
        .size()
        .rename(columns={"size": "QtdVezes"})
    )

    filtrado = primeira.merge(contagem, on="ContatoUUID", how="left")

    df_contatos = pd.DataFrame(contatos)
    df_contatos["Estado"] = df_contatos["fields"].apply(lambda f: (f or {}).get("estado"))
    df_contatos["Analista"] = df_contatos["fields"].apply(lambda f: (f or {}).get("analista"))
    df_contatos["Hunter"] = df_contatos["fields"].apply(lambda f: (f or {}).get("hunter"))
    df_contatos = df_contatos[["uuid", "Estado", "Analista", "Hunter"]].rename(
        columns={"uuid": "ContatoUUID"}
    )

    final = filtrado.merge(df_contatos, on="ContatoUUID", how="left", indicator="_merge")
    final["TemCadastro"] = final["_merge"] == "both"
    final = final.drop(columns=["_merge"])

    final["HunterNorm"] = final["Hunter"].fillna("").astype(str).str.strip().str.lower()
    resultado = final[final["HunterNorm"] == VALOR_HUNTER_ALVO].copy()

    resultado = resultado[
        ["ContatoUUID", "Nome", "text", "Estado", "Analista", "Hunter", "TemCadastro", "QtdVezes"]
    ]
    return resultado


def main():
    mensagens = atualizar_mensagens()
    contatos = atualizar_contatos()

    resultado = montar_relatorio(mensagens, contatos)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    resultado.to_excel(OUTPUT_PATH, index=False)
    print(f"Relatório gerado: {OUTPUT_PATH} ({len(resultado)} linhas)")


if __name__ == "__main__":
    main()
