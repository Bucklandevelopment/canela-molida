"""Streamlit dashboard para revisar y publicar drafts de Instagram.

Run:
    streamlit run frontend/instagram_app.py --server.port 8502
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:3690")
INSTAGRAM_API = f"{API_URL}/api/instagram"

st.set_page_config(
    page_title="canela-molida — Instagram drafts",
    page_icon=":sparkles:",
    layout="wide",
)

# Apply the UTOP.IA canonical dark theme (fonts, neon accents, glass)
from ds_theme import inject_design_css

inject_design_css(st)


def _get(path: str, **params) -> dict | list:
    r = httpx.get(f"{INSTAGRAM_API}{path}", params=params, timeout=30.0)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: Optional[dict] = None, timeout: float = 600.0) -> dict:
    r = httpx.post(f"{INSTAGRAM_API}{path}", json=json or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


# -- Sidebar -----------------------------------------------------------------

st.sidebar.title("📸 Instagram drafts")
status_filter = st.sidebar.selectbox(
    "Filter status",
    options=["all", "draft", "approved", "published", "rejected", "failed"],
    index=1,
)
limit = st.sidebar.slider("Show", 5, 100, 25)

st.sidebar.divider()
st.sidebar.subheader("Generate new draft")
gen_source = st.sidebar.selectbox("Source", ["local", "arxiv"])
gen_arxiv_id = st.sidebar.text_input("arXiv id (optional)", "")
gen_paper_id = st.sidebar.text_input("Local paper_id (optional)", "")
gen_category = st.sidebar.text_input("arXiv category (optional)", "")
gen_instructions = st.sidebar.text_area("Editorial notes (optional)", "")

if st.sidebar.button("Generate", type="primary", use_container_width=True):
    payload: dict = {"source": gen_source}
    if gen_arxiv_id.strip():
        payload["arxiv_id"] = gen_arxiv_id.strip()
    if gen_paper_id.strip():
        payload["paper_id"] = gen_paper_id.strip()
    if gen_category.strip():
        payload["category"] = gen_category.strip()
    if gen_instructions.strip():
        payload["instructions"] = gen_instructions.strip()
    with st.spinner("Generando con Ollama + Stable Diffusion…"):
        try:
            new_draft = _post("/drafts", json=payload, timeout=900.0)
            st.sidebar.success(f"Draft creado: {new_draft['id'][:8]}")
        except httpx.HTTPStatusError as e:
            st.sidebar.error(f"{e.response.status_code}: {e.response.text}")
        except Exception as exc:
            st.sidebar.error(str(exc))

# -- Main --------------------------------------------------------------------

st.title("Drafts pendientes")

drafts: list = []
try:
    list_params: dict = {"limit": limit}
    if status_filter != "all":
        list_params["status"] = status_filter
    result = _get("/drafts", **list_params)
    drafts = result if isinstance(result, list) else []
except Exception as exc:
    st.error(f"No se pudo conectar a la API ({INSTAGRAM_API}): {exc}")
    st.stop()

if not drafts:
    st.info("No hay drafts. Genera uno desde el sidebar.")
    st.stop()

for draft in drafts:
    with st.container(border=True):
        cols = st.columns([1, 2])

        with cols[0]:
            if draft.get("image_path"):
                img_name = os.path.basename(draft["image_path"])
                st.image(f"{INSTAGRAM_API}/images/{img_name}", width=320)
            else:
                st.warning("Sin imagen")
            st.caption(
                f"`{draft['paper_id']}` · {draft.get('paper_year') or '—'} "
                f"· **{draft['status'].upper()}**"
            )

        with cols[1]:
            content = draft.get("content", {})
            st.subheader(content.get("hook") or draft["paper_title"])
            st.markdown(content.get("caption", ""))
            tags = content.get("hashtags") or []
            if tags:
                st.write(" ".join(f"`#{t}`" for t in tags))
            with st.expander("Detalles técnicos"):
                st.write("**Authors:**", ", ".join(draft.get("paper_authors") or []) or "—")
                st.write("**Alt text:**", content.get("alt_text") or "—")
                st.write("**Image prompt:**", content.get("image_prompt") or "—")
                st.write("**Negative:**", content.get("image_negative_prompt") or "—")
                if draft.get("ig_permalink"):
                    st.write("**Permalink:**", draft["ig_permalink"])
                if draft.get("error"):
                    st.error(draft["error"])

            actions = st.columns(5)
            disabled_pub = draft["status"] in ("published", "rejected")

            if actions[0].button(
                "Aprobar", key=f"ap_{draft['id']}", disabled=disabled_pub
            ):
                _post(f"/drafts/{draft['id']}/approve", json={"publish_now": False})
                st.rerun()

            if actions[1].button(
                "Aprobar + publicar",
                key=f"app_{draft['id']}",
                type="primary",
                disabled=disabled_pub,
            ):
                _post(f"/drafts/{draft['id']}/approve", json={"publish_now": True})
                st.rerun()

            if actions[2].button(
                "Regenerar caption",
                key=f"rc_{draft['id']}",
                disabled=draft["status"] == "published",
            ):
                with st.spinner("LLM trabajando…"):
                    _post(
                        f"/drafts/{draft['id']}/regenerate",
                        json={"regenerate_caption": True, "regenerate_image": False},
                    )
                st.rerun()

            if actions[3].button(
                "Regenerar imagen",
                key=f"ri_{draft['id']}",
                disabled=draft["status"] == "published",
            ):
                with st.spinner("Renderizando imagen…"):
                    _post(
                        f"/drafts/{draft['id']}/regenerate",
                        json={"regenerate_caption": False, "regenerate_image": True},
                        timeout=600.0,
                    )
                st.rerun()

            if actions[4].button(
                "Descartar",
                key=f"rj_{draft['id']}",
                disabled=draft["status"] == "published",
            ):
                _post(f"/drafts/{draft['id']}/reject")
                st.rerun()
