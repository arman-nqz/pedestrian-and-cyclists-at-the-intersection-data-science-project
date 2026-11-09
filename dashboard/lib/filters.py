"""Sidebar filters shared by all pages. Values live in st.session_state and in the URL (shareable views)."""
import streamlit as st

from lib import data

DEFAULTS = {"variant": "clean", "classes": ["Pedestrian", "Cyclist", "Motorcycle"], "t_from": 0, "t_to": 96}


def _from_url():
    qp = st.query_params
    if "variant" in qp and qp["variant"] in data.VARIANTS:
        st.session_state.setdefault("variant", qp["variant"])
    if "classes" in qp:
        cl = [c for c in qp["classes"].split(",") if c in data.CLASSES]
        if cl:
            st.session_state.setdefault("classes", cl)
    if "t" in qp:
        try:
            a, b = (int(v) for v in qp["t"].split("-"))
            st.session_state.setdefault("time", (max(0, a), min(96, b)))
        except ValueError:
            pass


def sidebar(show_time=True, show_classes=True):
    """Draw the sidebar and return the active filters as a dict."""
    _from_url()
    st.session_state.setdefault("variant", DEFAULTS["variant"])
    st.session_state.setdefault("classes", DEFAULTS["classes"])
    st.session_state.setdefault("time", (DEFAULTS["t_from"], DEFAULTS["t_to"]))

    with st.sidebar:
        st.markdown("### Filters")
        variant = st.selectbox("Cleaning variant", data.VARIANTS, key="variant",
                               help="\n".join(f"- **{k}**: {v}" for k, v in data.VARIANT_HELP.items()))
        if variant == "clean":
            st.caption("`clean` drops tracks that barely move, about 83% of pedestrian tracks, "
                       "possibly including people who wait. See **Data quality**.")
        classes = st.multiselect("Classes", data.CLASSES, key="classes") if show_classes else st.session_state["classes"]
        t = st.session_state["time"]
        if show_time:
            t = st.select_slider("Time (local)", options=list(range(97)), key="time",
                                 format_func=lambda b: "24:00" if b == 96 else data.bin_label(b))
        st.markdown(f"**Active variant:** `{variant}`")

    st.query_params.update({"variant": variant, "classes": ",".join(classes), "t": f"{t[0]}-{t[1]}"})
    return {"variant": variant, "classes": classes, "t_from": t[0], "t_to": t[1]}


def limits_box():
    st.info(
        "**Limits.** One recorded day (14 Oct 2026). Near-miss events are algorithm candidates, not collisions, "
        "and are not normalized by traffic volume. There is no scooter class (scooters are probably counted as "
        "cyclists or pedestrians). No traffic-signal data yet. The OpenStreetMap layer is aligned to the sensor "
        "to about 2 m."
    )
