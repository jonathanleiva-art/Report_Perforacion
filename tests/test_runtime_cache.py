from runtime_cache import cache_data, cache_resource


def test_cache_data_cachea_y_clear_limpia():
    llamadas = []

    @cache_data
    def duplicar(valor):
        llamadas.append(valor)
        return {"items": [valor * 2]}

    primero = duplicar(2)
    primero["items"].append(99)
    segundo = duplicar(2)

    assert llamadas == [2]
    assert segundo == {"items": [4]}

    duplicar.clear()
    assert duplicar(2) == {"items": [4]}
    assert llamadas == [2, 2]


def test_cache_resource_reusa_misma_instancia():
    @cache_resource
    def crear_lista():
        return []

    primero = crear_lista()
    primero.append("valor")

    assert crear_lista() is primero
    assert crear_lista() == ["valor"]
