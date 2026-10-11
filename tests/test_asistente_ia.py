"""Chat de Shaki con y sin IA: enrutador, bucle de herramientas de Claude (simulado) y SQL de solo lectura."""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from config import cfg  # noqa: E402
from database import inicializar_db  # noqa: E402
from modulos import asistente as a  # noqa: E402
from modulos import asistente_datos as ad  # noqa: E402


@pytest.fixture(autouse=True)
def _bd(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "ia.db"))
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "")
    inicializar_db()


def _b(tipo, **kw):
    return types.SimpleNamespace(type=tipo, **kw)


class _ClienteFalso:
    """Imita anthropic.Anthropic: 1.ª llamada pide herramientas (con razonamiento), 2.ª responde."""

    def __init__(self, *a, **k):
        self.llamadas = []
        self.messages = self

    def create(self, **kw):
        self.llamadas.append(kw)
        uso = types.SimpleNamespace(input_tokens=100, output_tokens=20, cache_creation_input_tokens=0)
        if len(self.llamadas) == 1:
            return types.SimpleNamespace(stop_reason="tool_use", usage=uso, content=[
                _b("thinking", thinking="Necesito caja y proveedores", signature="x"),
                _b("tool_use", id="t1", name="sql", input={"consulta": "SELECT COUNT(*) n FROM log_acciones"}),
                _b("tool_use", id="t2", name="no_existe", input={})])
        return types.SimpleNamespace(stop_reason="end_turn", usage=uso,
                                     content=[_b("thinking", thinking="ok", signature="y"), _b("text", text="Análisis listo")])


def test_bucle_de_herramientas_con_claude(monkeypatch):
    falso = _ClienteFalso()
    fake_mod = types.SimpleNamespace(Anthropic=lambda **k: falso, BadRequestError=Exception)
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-ant-prueba")
    r = a.responder("¿Por qué perdimos plata en junio y qué recomiendas?")  # analítica → va a Claude
    assert r == "Análisis listo"
    segunda = falso.llamadas[1]
    assert segunda["model"] == cfg.MODELO_COMPLEJO
    assert segunda["extra_body"] == {"output_config": {"effort": cfg.IA_ESFUERZO}}
    asis, res = segunda["messages"][-2], segunda["messages"][-1]
    assert asis["content"][0].type == "thinking"  # el razonamiento se devuelve tal cual
    contenidos = {x["tool_use_id"]: x["content"] for x in res["content"]}
    assert '"n":' in contenidos["t1"] and "desconocida" in contenidos["t2"]
    assert falso.llamadas[0]["tools"][-1]["cache_control"] == {"type": "ephemeral"}


def test_enrutador(monkeypatch):
    assert not a._necesita_ia("pagos de esta semana", [])
    assert a._necesita_ia("por qué bajaron las ventas en junio", [])
    assert a._necesita_ia("y en agosto?", [{"role": "user", "content": "x"}])
    assert not a._necesita_ia("y en agosto?", [])
    llamado = []
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-ant-prueba")
    monkeypatch.setattr(a, "_con_claude", lambda p, h: llamado.append(p) or "IA")
    assert a.responder("hola") .startswith("¡Hola!") and not llamado     # simple: gratis, sin IA
    assert a.responder("asdf qwer zxcv") == "IA"                          # el local no entendió: IA
    assert a.responder("analiza la cartera") == "IA"                      # analítica: IA


def test_sin_clave_nunca_llama_a_claude(monkeypatch):
    monkeypatch.setattr(a, "_con_claude", lambda p, h: (_ for _ in ()).throw(AssertionError("no debía llamar")))
    for q in ["por qué perdimos plata", "asdf", "cómo vamos", "cuánta plata hay en bancos", "me alcanza la plata"]:
        assert isinstance(a.responder(q), str)


def test_si_claude_falla_responde_el_local(monkeypatch):
    monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-ant-prueba")
    monkeypatch.setattr(a, "_con_claude", lambda p, h: (_ for _ in ()).throw(RuntimeError("sin internet")))
    r = a.responder("por qué no hay pagos esta semana")
    assert "modo local" in r


def test_sql_solo_lectura():
    assert ad.h_sql("SELECT COUNT(*) n FROM log_acciones")["filas"][0]["n"] >= 0
    for malo in ["DELETE FROM log_acciones", "SELECT 1; DROP TABLE x", "UPDATE alertas SET resuelto=1",
                 "WITH x AS (SELECT 1) DELETE FROM alertas"]:
        assert "error" in ad.h_sql(malo)
    assert all(t["filas"] > 0 and t["columnas"] for t in ad.h_esquema()["tablas"])  # solo tablas con datos
    assert "columnas" in ad.h_esquema("log_acciones") and "error" in ad.h_esquema("no_existe")
