"""
Location request — Streamlit Community Cloud demo.

Driver link :  https://YOUR-APP.streamlit.app/?ref=JOB-4417&from=Dispatch
Your view   :  https://YOUR-APP.streamlit.app/?view=admin&key=change-me
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st
from streamlit_js_eval import get_geolocation

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
ADMIN_KEY = "change-me"          # change this before you share the link
LOG = Path("locations.jsonl")    # ephemeral: wiped when the app restarts
GOOD_ACCURACY_M = 60

st.set_page_config(page_title="Location request", page_icon="📍",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  #MainMenu, footer, header {visibility:hidden;}
  .block-container {padding-top:2.2rem; max-width:640px;}
  .card {border:1.5px solid #152230; background:#F3F6F7; padding:18px 20px; margin-bottom:14px;}
  .band {background:#152230; color:#F3F6F7; font-family:ui-monospace,monospace;
         font-size:11px; letter-spacing:.18em; text-transform:uppercase;
         padding:7px 20px; margin:-18px -20px 16px;}
  .k {font-family:ui-monospace,monospace; font-size:10px; letter-spacing:.15em;
      text-transform:uppercase; color:#5A6B7A;}
  .v {font-family:ui-monospace,monospace; font-size:16px; color:#152230;}
  .addr {font-size:18px; font-weight:600; line-height:1.35; color:#152230;}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------
def save(record: dict) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_all() -> list:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> str | None:
    """Street address from coordinates. Free, no API key, rate-limited."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lon,
                    "zoom": 18, "addressdetails": 1},
            headers={"User-Agent": "location-demo/1.0"},
            timeout=8,
        )
        r.raise_for_status()
        return r.json().get("display_name")
    except Exception:
        return None


# ----------------------------------------------------------------------
# Dispatcher view
# ----------------------------------------------------------------------
def admin_view():
    st.title("Locations received")
    rows = load_all()

    if not rows:
        st.info("Nothing yet. Send someone the driver link and it will appear here.")
    else:
        for r in reversed(rows):
            with st.container(border=True):
                st.markdown(f"**{r.get('address') or 'No address found'}**")
                if r.get("note"):
                    st.caption(f"Note: {r['note']}")
                st.caption(
                    f"{r['ref']} · ±{r['accuracy_m']} m · "
                    f"{r['received_at'][11:19]} UTC · "
                    f"[map](https://www.google.com/maps?q={r['latitude']},{r['longitude']})"
                )
        st.download_button("Download all as JSON",
                           json.dumps(rows, indent=2),
                           "locations.json", "application/json")

    st.divider()
    st.caption(
        "Stored in a file on the app container. Streamlit Community Cloud wipes "
        "this whenever the app sleeps or redeploys — download anything you need to keep."
    )
    if st.button("Refresh"):
        st.rerun()


# ----------------------------------------------------------------------
# Driver view
# ----------------------------------------------------------------------
def driver_view(ref: str, requester: str):
    if st.session_state.get("saved"):
        show_result()
        return

    st.markdown(
        f'<div class="card"><div class="band">Location request · {ref}</div>'
        f'<div style="font-size:22px;font-weight:650;line-height:1.2;margin-bottom:8px">'
        f'Where are you right now?</div>'
        f'<div style="color:#5A6B7A;font-size:15px">{requester} needs your exact stop '
        f'so nobody has to spell out a postcode. Your phone will ask permission — '
        f'tap Allow.</div></div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Waiting for your phone…"):
        loc = get_geolocation()

    if not loc:
        st.warning(
            "**No position yet.** If you saw a permission prompt, tap Allow. "
            "If you tapped Block, reopen the permission from the padlock or ⚙ icon "
            "in the address bar, then reload.\n\n"
            "If you opened this from WhatsApp or Instagram, use the ⋯ menu → "
            "**Open in browser** — chat apps block location."
        )
        if st.button("Try again", type="primary", use_container_width=True):
            st.rerun()
        return

    coords = loc.get("coords", {})
    lat, lon = coords.get("latitude"), coords.get("longitude")
    acc = round(coords.get("accuracy", 0))

    if lat is None:
        st.error("Got a response with no coordinates. Reload and try again.")
        return

    address = reverse_geocode(lat, lon)

    st.markdown(
        f'<div class="card">'
        f'<div class="addr">{address or "No address found — coordinates only"}</div>'
        f'<div style="margin-top:12px"><span class="k">Coordinates</span><br>'
        f'<span class="v">{lat:.6f}, {lon:.6f}</span></div>'
        f'<div style="margin-top:10px"><span class="k">Accuracy</span><br>'
        f'<span class="v">±{acc} m</span></div></div>',
        unsafe_allow_html=True,
    )

    if acc > 150:
        st.warning(
            f"±{acc} m is a network estimate, not GPS. If you are indoors or under "
            "cover, step outside and reload for a proper fix."
        )

    st.link_button("Check it on a map",
                   f"https://www.google.com/maps?q={lat},{lon}",
                   use_container_width=True)

    note = st.text_input("Add a detail (optional)",
                         placeholder="e.g. Gate 3, rear yard, buzzer B",
                         max_chars=80)

    if st.button("Send this location", type="primary", use_container_width=True):
        record = {
            "ref": ref,
            "requester": requester,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "accuracy_m": acc,
            "address": address,
            "note": note.strip() or None,
            "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        save(record)
        st.session_state["saved"] = record
        st.rerun()


def show_result():
    r = st.session_state["saved"]
    st.success(f"Sent to {r['requester']}.")
    st.markdown(
        f'<div class="card"><div class="band">Confirmed · {r["ref"]}</div>'
        f'<div class="addr">{r["address"] or "Coordinates only"}</div>'
        f'<div style="margin-top:10px"><span class="v">{r["latitude"]}, '
        f'{r["longitude"]}</span> <span class="k">±{r["accuracy_m"]} m</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption("You can close this page. It will not report your position again.")


# ----------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------
qp = st.query_params

if qp.get("view") == "admin":
    if qp.get("key") == ADMIN_KEY:
        admin_view()
    else:
        st.error("Wrong key.")
else:
    driver_view(
        ref=qp.get("ref", f"REF-{int(time.time()) % 100000}"),
        requester=qp.get("from", "Dispatch"),
    )
