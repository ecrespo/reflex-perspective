"""Compile-level tests for the PerspectiveViewer component and actions."""

import reflex as rx

import reflex_perspective as rp


class S(rx.State):
    rows: list[dict] = [{"a": 1}]
    cfg: dict = {"plugin": "Y Bar"}
    layouts: dict[str, dict] = {"x": {"group_by": ["a"]}}

    @rx.event
    def got(self, value: dict):
        pass


def render(component: rx.Component) -> str:
    return str(component)


def test_props_are_camel_cased():
    js = render(
        rp.perspective_viewer(
            id="v",
            data=S.rows,
            group_by=["a"],
            split_by=["b"],
            server_url="/perspective",
            server_table="t",
            update_rows=S.rows,
            edit_mode="EDIT",
        )
    )
    for prop in (
        "groupBy",
        "splitBy",
        "serverUrl",
        "serverTable",
        "updateRows",
        "editMode",
    ):
        assert prop in js


def test_event_triggers_forward_payload():
    js = render(
        rp.perspective_viewer(
            on_click=S.got, on_config_update=S.got, on_select=S.got, on_load=S.got
        )
    )
    for trigger in ("onClick", "onConfigUpdate", "onSelect", "onLoad"):
        assert trigger in js
    assert "_detail" in js


def test_library_points_to_shared_bridge():
    comp = rp.perspective_viewer()
    assert comp.library.startswith("$/public")
    assert comp.library.endswith("perspective_viewer.jsx")
    assert all(dep.endswith(rp.PERSPECTIVE_VERSION) for dep in comp.lib_dependencies)


def test_children_rejected():
    try:
        rp.perspective_viewer(rx.text("x"))
    except ValueError:
        return
    raise AssertionError("children should be rejected")


def _fn_expr(spec) -> str:
    args = {str(k): v for k, v in spec.args}
    return str(args["function"])


def test_actions_with_literals():
    assert (
        _fn_expr(rp.download("v", "arrow"))
        == '(() => window.reflexPerspective.download("v", "arrow"))'
    )
    assert "toggleConfig" in _fn_expr(rp.toggle_config("v"))
    assert '"group_by"' in _fn_expr(rp.restore("v", {"group_by": ["a"]}))


def test_actions_with_state_vars_keep_var_data():
    spec = rp.restore("v", S.cfg)
    fn = {str(k): v for k, v in spec.args}["function"]
    assert fn._get_all_var_data() is not None


def test_actions_unwrap_mutable_proxies():
    from reflex.istate.proxy import MutableProxy

    state = S(_reflex_internal_init=True)  # type: ignore[call-arg]
    proxy = MutableProxy(state.layouts["x"], state, "layouts")
    assert '"group_by"' in _fn_expr(rp.restore("v", proxy))


def test_callback_actions():
    spec = rp.save("v", S.got)
    args = {str(k): v for k, v in spec.args}
    assert "addEvents" in str(args["callback"])


def test_constants():
    assert "Datagrid" in rp.PLUGINS and "Treemap" in rp.PLUGINS
    assert "Pro Dark" in rp.THEMES
    assert "sum" in rp.AGGREGATES
