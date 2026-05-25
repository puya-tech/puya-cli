"""Tests directos de parse_ids y parse_json en commands/_helpers.

Donde se rompen más cosas en la práctica: input mal formado del usuario
o de un agente. Las funciones existen acá, no las re-testeo a través de
cada comando que las usa.
"""

from __future__ import annotations

import pytest
import typer

from puya.commands._helpers import parse_domain, parse_ids, parse_json


class TestParseIds:
    def test_csv_simple(self):
        assert parse_ids("1,2,3") == [1, 2, 3]

    def test_csv_con_espacios(self):
        assert parse_ids(" 1, 2 , 3 ") == [1, 2, 3]

    def test_single_id(self):
        assert parse_ids("42") == [42]

    def test_json_list(self):
        assert parse_ids("[1,2,3]") == [1, 2, 3]

    def test_json_list_vacia_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_ids("[]")
        assert exc.value.exit_code == 1

    def test_csv_invalido_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_ids("1,abc,3")
        assert exc.value.exit_code == 1

    def test_json_no_array_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_ids('{"id": 1}')
        assert exc.value.exit_code == 1

    def test_json_array_con_string_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_ids('[1, "two", 3]')
        assert exc.value.exit_code == 1

    def test_json_malformado_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_ids("[1, 2,")
        assert exc.value.exit_code == 1


class TestParseJson:
    def test_objeto_valido(self):
        assert parse_json("values", '{"a": 1}') == {"a": 1}

    def test_array_valido(self):
        assert parse_json("args", "[1, 2, 3]") == [1, 2, 3]

    def test_scalar_valido(self):
        assert parse_json("x", "42") == 42

    def test_malformado_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_json("values", "{not json}")
        assert exc.value.exit_code == 1


class TestParseDomain:
    def test_lista_vacia(self):
        assert parse_domain("[]") == []

    def test_lista_valida_odoo(self):
        assert parse_domain('[["active","=",true]]') == [["active", "=", True]]

    def test_string_no_es_dominio_sale_1(self):
        """Bug atrapado en review 2026-05-24: '"foo"' es JSON válido pero
        no es dominio Odoo. El server lo trataba como dominio vacío
        silenciosamente. Ahora falla antes de pegarle al server."""
        with pytest.raises(typer.Exit) as exc:
            parse_domain('"not a list"')
        assert exc.value.exit_code == 1

    def test_objeto_no_es_dominio_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_domain('{"x": 1}')
        assert exc.value.exit_code == 1

    def test_numero_no_es_dominio_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_domain("42")
        assert exc.value.exit_code == 1

    def test_json_malformado_sale_1(self):
        with pytest.raises(typer.Exit) as exc:
            parse_domain("[")
        assert exc.value.exit_code == 1
